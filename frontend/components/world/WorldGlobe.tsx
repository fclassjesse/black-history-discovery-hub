"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, Marker } from "maplibre-gl";
import { useWorld } from "@/lib/worldStore";
import { useSelection } from "@/lib/store";
import { prefersReducedMotion } from "@/lib/motion";
import { applyPaperAtlas } from "@/components/world/worldPalette";
import { worldHandle } from "@/components/world/worldHandle";
import { PinMarker } from "@/components/world/PinMarker";
import { GlobeHalo } from "@/components/world/GlobeHalo";
import { arrivalCoords, easeToBounds } from "@/components/world/worldCamera";
import { character } from "@/lib/character";
import type { Pin } from "@/lib/types";
import { useT } from "@/lib/i18n";

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
/** The Black Atlantic: between Nova Scotia, the Caribbean and West Africa. */
const IDLE_CENTER: [number, number] = [-40, 30];
/** Idle motion: the world keeps turning (one revolution per IDLE_SPIN_PERIOD_S), pausing while you touch it or hover a pin. */
const IDLE_SPIN_PERIOD_S = 80;
const RESUME_AFTER_MS = 4500;
/** MapLibre's perspective camera shows a little less than a hemisphere: the visible rim is ~0.92 of the sphere radius at idle zooms. */
const HORIZON_SHRINK = 0.92;
/** While a search is in flight the camera glides toward Atlantic Canada / the US east coast, where most holders are. */
const SEARCH_VANTAGE: [number, number] = [-64, 41];
const PENDING_ZOOM_IN = 0.9;
/** Long on purpose: still easing (slowly) when a slow search answers, so the arrival continues the motion. */
const PENDING_GLIDE_MS = 7000;
/** Arrival fit: a direct glide (no zoom-out-then-in arc) and a zoom cap that keeps tile loading light mid-flight. */
const ARRIVAL_MS = 1700;
const FIT_MAX_ZOOM = 8;
const SINGLE_PIN_ZOOM = 7.5;
const easeOutQuint = (t: number) => 1 - Math.pow(1 - t, 5);
const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

if (typeof window !== "undefined") maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

/** MapLibre's "hold ⌘/Ctrl and scroll to zoom" overlay is unwanted (owner request 2026-11-07). The handler rebuilds
 *  the element every time cooperative gestures are re-enabled, so it is hidden inline here as well as in globals.css. */
function hideGestureHint(map: MLMap) {
  map.getContainer().querySelectorAll<HTMLElement>(".maplibregl-cooperative-gesture-screen").forEach((el) => {
    el.style.display = "none";
  });
}

function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return Boolean(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

interface PortalEntry { id: string; el: HTMLElement; pin: Pin; order: number }

export default function WorldGlobe() {
  const { t } = useT();
  // the map is created once; its help texts are read through a ref so the effect does not depend on `t`
  const tRef = useRef(t);
  useEffect(() => { tRef.current = t; }, [t]);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<Map<string, { marker: Marker; el: HTMLElement }>>(new Map());
  const lastInteractionRef = useRef(0);
  const [ready, setReady] = useState(false);
  const [mapObj, setMapObj] = useState<MLMap | null>(null);
  const enteredRef = useRef(false);
  const [portals, setPortals] = useState<PortalEntry[]>([]);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const hoverRef = useRef<string | null>(null);
  useEffect(() => { hoverRef.current = hoverId; }, [hoverId]);

  const { pins, recordsById, mode, inset, projection, pending, setWebgl, setStatus } = useWorld();
  const { selectedInstitutionId, selectInstitution, focusInstitutionIds, selectedRecordId } = useSelection();

  // ---- create the map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    if (!hasWebGL()) { setWebgl(false); setStatus("error"); return; }
    setWebgl(true);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: IDLE_CENTER,
      zoom: 1.6,
      pitch: 0,
      attributionControl: false,
      cooperativeGestures: true,
      locale: {
        "CooperativeGesturesHandler.WindowsHelpText": tRef.current("world.windowsHelp"),
        "CooperativeGesturesHandler.MacHelpText": tRef.current("world.macHelp"),
        "CooperativeGesturesHandler.MobileHelpText": tRef.current("world.mobileHelp"),
      },
      fadeDuration: 200,
      canvasContextAttributes: { antialias: true, alpha: true },
    });
    hideGestureHint(map);
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
    map.on("style.load", () => {
      applyPaperAtlas(map);
      try {
        map.setProjection({ type: useWorld.getState().projection === "globe" ? "globe" : "mercator" });
        map.setSky({ "atmosphere-blend": 0, "sky-color": "#f2612a", "horizon-color": "#f5c244", "fog-color": "#f2612a" });
      } catch (err) { console.warn("[world] projection unsupported, staying flat", err); useWorld.getState().setProjection("flat"); }
      setReady(true);
      setStatus("ready");
    });
    map.on("error", (e) => { if (e?.error) console.warn("[world]", e.error.message ?? e.error); });
    map.on("click", (e) => { if ((e.originalEvent?.target as HTMLElement | null)?.closest?.(".pin-root")) return; selectInstitution(null); });
    const touch = () => { lastInteractionRef.current = performance.now(); };
    for (const ev of ["mousedown", "touchstart", "wheel"] as const) map.getCanvasContainer().addEventListener(ev, touch, { passive: true });
    mapRef.current = map;
    worldHandle.map = map;
    setMapObj(map);
    (window as unknown as { __BHDH_WORLD__?: MLMap }).__BHDH_WORLD__ = map; // handy for the designer and for debugging
    const markers = markersRef.current;
    return () => {
      for (const ev of ["mousedown", "touchstart", "wheel"] as const) map.getCanvasContainer().removeEventListener(ev, touch);
      markers.forEach((m) => m.marker.remove());
      markers.clear();
      map.remove();
      mapRef.current = null;
      worldHandle.map = null;
      setMapObj(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- projection toggle (globe ⇄ flat)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    try { map.setProjection({ type: projection === "globe" ? "globe" : "mercator" }); } catch { /* ignore */ }
  }, [projection, ready]);

  // ---- interaction policy per mode. Stage: fully zoomable, but cooperative (⌘/Ctrl + wheel, two fingers) so the
  // page still scrolls. Results: every gesture goes straight to the world.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.scrollZoom.enable();
    map.doubleClickZoom.enable();
    map.dragPan.enable();
    map.dragRotate.enable();
    map.touchZoomRotate.enable();
    if (mode === "idle") { map.cooperativeGestures.enable(); hideGestureHint(map); map.keyboard.disable(); }
    else { map.cooperativeGestures.disable(); map.keyboard.enable(); }
  }, [mode, ready]);

  // ---- anticipation: the moment a question is asked the world stops turning and starts one long, decelerating glide
  // toward the collection's home waters. The search can take a few seconds; the camera must still be moving (slowly)
  // when the results land so the fit continues the motion instead of starting from a frozen globe. Heading for the
  // region where most holders are also shortens the final flight, so fewer tiles load mid-move.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !pending || prefersReducedMotion() || useWorld.getState().mode !== "idle") return;
    lastInteractionRef.current = performance.now(); // pauses the idle spin (it also stays off while pending)
    map.easeTo({ center: SEARCH_VANTAGE, zoom: map.getZoom() + PENDING_ZOOM_IN, pitch: 0, bearing: 0, duration: PENDING_GLIDE_MS, easing: easeOutQuint, essential: true });
  }, [pending, ready]);

  // ---- camera: idle composition or fit to result pins (the first idle → results move is the long, cinematic one)
  const pinKey = pins.map((p) => `${p.institution.id}:${p.count}`).join("|");
  const prevModeRef = useRef<"idle" | "results">("idle");
  /** True while the first idle → results fit is flying; guide focus waits for it instead of cutting it off. */
  const arrivalRef = useRef(false);
  /** Once the idle composition is placed we leave the spinning world alone (pins re-publishing must not yank it back). */
  const idlePlacedRef = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const reduce = prefersReducedMotion();
    const arriving = prevModeRef.current === "idle" && mode === "results";
    prevModeRef.current = mode;
    const dur = (normal: number) => (reduce ? 0 : arriving ? Math.max(normal, 1700) : normal);
    const w = map.getContainer().clientWidth;
    const h = map.getContainer().clientHeight;
    const pad = { left: Math.round(inset.left * w), top: Math.round(inset.top * h), right: Math.round(inset.right * w), bottom: Math.round(inset.bottom * h) };
    const goIdle = () => {
      const compact = w < 1024;
      // the sphere as a big paper ball filling the right half (its far edge may kiss the viewport edge) or peeking under the bar (phones)
      const radius = compact ? w * 0.7 : Math.min(h * 0.5, w * 0.32);
      const zoom = Math.max(0.8, Math.log2(((radius / HORIZON_SHRINK) * 2 * Math.PI) / 512));
      const padding = compact
        ? { left: 0, right: 0, top: Math.round(h * 0.7), bottom: 0 }
        : { left: Math.round(w * 0.48), right: 0, top: Math.round(h * 0.06), bottom: 0 };
      const first = !enteredRef.current;
      enteredRef.current = true;
      if (first && !reduce) {
        // entrance: the world rolls in from far away and settles
        map.jumpTo({ center: [IDLE_CENTER[0] + 90, IDLE_CENTER[1] - 10], zoom: Math.max(0.5, zoom - 1.1), pitch: 0, bearing: 0, padding });
        map.easeTo({ center: IDLE_CENTER, zoom, pitch: 0, bearing: 0, padding, duration: 2400, easing: (t) => 1 - Math.pow(1 - t, 3) });
        return;
      }
      map.easeTo({ center: IDLE_CENTER, zoom, pitch: 0, bearing: 0, padding, duration: reduce ? 0 : 1600, easing: (t) => 1 - Math.pow(1 - t, 3) });
    };
    worldHandle.reset = goIdle;
    if (mode === "idle") {
      if (!idlePlacedRef.current) goIdle();
      idlePlacedRef.current = true;
      return;
    }
    idlePlacedRef.current = false;
    const coords = arrivalCoords(pins);
    const padding = { left: pad.left + 56, top: pad.top + 72, right: pad.right + 56, bottom: pad.bottom + 72 };
    // Arrival: the pending glide is slowing down by now, so an ease-in-out picks it up without a jolt, and easeTo
    // (linear path) avoids flyTo's zoom-out-then-in bump, which read as a hiccup and loaded extra tile levels.
    const ease = { duration: dur(ARRIVAL_MS), easing: easeInOutCubic, essential: true } as const;
    worldHandle.reset = () => {
      if (coords.length === 0) { map.easeTo({ center: [-63.6, 44.9], zoom: 4.5, pitch: 0, bearing: 0, padding, ...ease }); return; }
      if (coords.length === 1) { map.easeTo({ center: coords[0], zoom: SINGLE_PIN_ZOOM, pitch: 30, bearing: 0, padding, ...ease }); return; }
      let fitted = false;
      try { fitted = easeToBounds(map, coords, padding, FIT_MAX_ZOOM, { pitch: 24, bearing: 0, ...ease }); } catch (err) { console.warn("[world] fit failed", err); }
      if (!fitted) map.easeTo({ center: coords[0], zoom: 4.5, pitch: 0, bearing: 0, padding, ...ease });
    };
    worldHandle.reset();
    // registered after the move starts: starting it fires moveend for the pending glide it interrupts
    if (arriving && !reduce && map.isMoving()) {
      arrivalRef.current = true;
      map.once("moveend", () => { arrivalRef.current = false; });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, pinKey, ready, inset.left, inset.top, inset.right, inset.bottom]);

  // ---- idle spin (pauses after any interaction or while a pin is hovered; never with reduced motion)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || mode !== "idle" || prefersReducedMotion()) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const idleFor = now - lastInteractionRef.current;
      if (idleFor > RESUME_AFTER_MS && !hoverRef.current && !useWorld.getState().pending && !map.isMoving() && document.visibilityState === "visible") {
        const c = map.getCenter();
        map.setCenter([c.lng - (dt / IDLE_SPIN_PERIOD_S) * 360, c.lat]);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [mode, ready]);

  // ---- markers: one per institution; React renders into them through portals
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const wanted = new Map(pins.filter((p) => p.institution.latitude != null && p.institution.longitude != null).map((p) => [p.institution.id, p]));
    const current = markersRef.current;
    for (const [id, m] of current) if (!wanted.has(id)) { m.marker.remove(); current.delete(id); }
    const entries: PortalEntry[] = [];
    let order = 0;
    for (const [id, pin] of wanted) {
      let m = current.get(id);
      if (!m) {
        const el = document.createElement("div");
        el.className = "pin-root";
        el.addEventListener("mouseenter", () => { setHoverId(id); if (useWorld.getState().mode === "idle") character.set("pointing", undefined, 1800); });
        el.addEventListener("mouseleave", () => setHoverId((h) => (h === id ? null : h)));
        const marker = new maplibregl.Marker({ element: el, anchor: "bottom", opacityWhenCovered: "0.1" }).setLngLat([pin.institution.longitude as number, pin.institution.latitude as number]).addTo(map);
        m = { marker, el };
        current.set(id, m);
      } else {
        m.marker.setLngLat([pin.institution.longitude as number, pin.institution.latitude as number]);
      }
      entries.push({ id, el: m.el, pin, order: order++ });
    }
    setPortals(entries);
  }, [pins, ready]);

  // raise the open marker above its siblings
  useEffect(() => {
    markersRef.current.forEach((m, id) => m.marker.getElement().classList.toggle("open", id === selectedInstitutionId));
  }, [selectedInstitutionId, portals]);

  // ---- selection / guide focus → glide to the institution
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || mode !== "results") return;
    const target = selectedInstitutionId ?? focusInstitutionIds[0];
    if (!target) return;
    const pin = pins.find((p) => p.institution.id === target);
    if (!pin || pin.institution.latitude == null || pin.institution.longitude == null) return;
    const center: [number, number] = [pin.institution.longitude, pin.institution.latitude];
    const glide = () => {
      const w = map.getContainer().clientWidth;
      const h = map.getContainer().clientHeight;
      map.flyTo({ center, zoom: Math.max(map.getZoom(), 7), padding: { left: Math.round(inset.left * w), top: Math.round(inset.top * h), right: Math.round(inset.right * w), bottom: Math.round(inset.bottom * h) }, offset: [0, 120], duration: prefersReducedMotion() ? 0 : 1100, essential: true });
    };
    // the guide often answers while the arrival fit is still flying: let that land first, then glide on
    if (!arrivalRef.current) { glide(); return; }
    map.once("moveend", glide);
    return () => { map.off("moveend", glide); };
  }, [selectedInstitutionId, focusInstitutionIds, selectedRecordId, pins, ready, mode, inset]);

  const portalNodes = useMemo(() => portals.map(({ id, el, pin, order }) => createPortal(
    <PinMarker pin={pin} order={order} recordsById={recordsById} open={selectedInstitutionId === id} hovered={hoverId === id} mode={mode} onToggle={() => selectInstitution(selectedInstitutionId === id ? null : id)} />,
    el,
    id,
  )), [portals, recordsById, selectedInstitutionId, hoverId, mode, selectInstitution]);

  return (
    <div className="world-root" data-pending={pending}>
      <div ref={containerRef} className="world-map" role="region" aria-label={t("world.region")} />
      {mapObj && ready && <GlobeHalo map={mapObj} />}
      {portalNodes}
    </div>
  );
}
