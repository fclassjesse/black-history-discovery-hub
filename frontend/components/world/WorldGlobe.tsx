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

if (typeof window !== "undefined") maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

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

  const { pins, recordsById, mode, inset, projection, setWebgl, setStatus } = useWorld();
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
    if (mode === "idle") { map.cooperativeGestures.enable(); map.keyboard.disable(); }
    else { map.cooperativeGestures.disable(); map.keyboard.enable(); }
  }, [mode, ready]);

  // ---- camera: idle composition or fit to result pins (the first idle → results move is the long, cinematic one)
  const pinKey = pins.map((p) => `${p.institution.id}:${p.count}`).join("|");
  const prevModeRef = useRef<"idle" | "results">("idle");
  /** Once the idle composition is placed we leave the spinning world alone (pins re-publishing must not yank it back). */
  const idlePlacedRef = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const reduce = prefersReducedMotion();
    const arriving = prevModeRef.current === "idle" && mode === "results";
    prevModeRef.current = mode;
    const dur = (normal: number) => (reduce ? 0 : arriving ? Math.max(normal, 2300) : normal);
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
    const coords = pins.filter((p) => p.institution.latitude != null && p.institution.longitude != null).map((p) => [p.institution.longitude as number, p.institution.latitude as number] as [number, number]);
    const padding = { left: pad.left + 56, top: pad.top + 72, right: pad.right + 56, bottom: pad.bottom + 72 };
    worldHandle.reset = () => {
      if (coords.length === 0) { map.flyTo({ center: [-63.6, 44.9], zoom: 4.5, pitch: 0, bearing: 0, padding, duration: dur(900), essential: true }); return; }
      if (coords.length === 1) { map.flyTo({ center: coords[0], zoom: 8.5, pitch: 30, bearing: 0, padding, duration: dur(1200), curve: 1.5, essential: true }); return; }
      const b = coords.reduce((bb, c) => bb.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
      try { map.fitBounds(b, { padding, maxZoom: 9, pitch: 24, bearing: 0, duration: dur(1400), curve: 1.5, essential: true }); }
      catch { map.flyTo({ center: b.getCenter(), zoom: 3, padding, duration: dur(1000), essential: true }); }
    };
    worldHandle.reset();
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
      if (idleFor > RESUME_AFTER_MS && !hoverRef.current && !map.isMoving() && document.visibilityState === "visible") {
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
    const w = map.getContainer().clientWidth;
    const h = map.getContainer().clientHeight;
    map.flyTo({ center: [pin.institution.longitude, pin.institution.latitude], zoom: Math.max(map.getZoom(), 7), padding: { left: Math.round(inset.left * w), top: Math.round(inset.top * h), right: Math.round(inset.right * w), bottom: Math.round(inset.bottom * h) }, offset: [0, 120], duration: prefersReducedMotion() ? 0 : 1100, essential: true });
  }, [selectedInstitutionId, focusInstitutionIds, selectedRecordId, pins, ready, mode, inset]);

  const portalNodes = useMemo(() => portals.map(({ id, el, pin, order }) => createPortal(
    <PinMarker pin={pin} order={order} recordsById={recordsById} open={selectedInstitutionId === id} hovered={hoverId === id} mode={mode} onToggle={() => selectInstitution(selectedInstitutionId === id ? null : id)} />,
    el,
    id,
  )), [portals, recordsById, selectedInstitutionId, hoverId, mode, selectInstitution]);

  return (
    <div className="world-root">
      <div ref={containerRef} className="world-map" role="region" aria-label={t("world.region")} />
      {mapObj && ready && <GlobeHalo map={mapObj} />}
      {portalNodes}
    </div>
  );
}
