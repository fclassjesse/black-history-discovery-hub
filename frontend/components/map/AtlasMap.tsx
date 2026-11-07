"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useSelection } from "@/lib/store";
import type { Pin, RecordCard } from "@/lib/types";
import { pinKind, useLabels } from "@/lib/labels";
import { useT, type Translator } from "@/lib/i18n";

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
// Turbopack cannot resolve MapLibre's worker relative to the bundle; serve the worker from /public.
if (typeof window !== "undefined") maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
const ATTRIBUTION = '© <a href="https://openfreemap.org">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';

interface Props {
  pins: Pin[];
  recordsById: Map<string, RecordCard>;
}

type Labels = ReturnType<typeof useLabels>;

function buildMarkerEl(pin: Pin, recordsById: Map<string, RecordCard>, open: boolean, onSelect: () => void, L: Labels, t: Translator["t"], tn: Translator["tn"], href: (h: string) => string): HTMLElement {
  const inst = pin.institution;
  const kind = pinKind(inst.location_precision, recordsById.get(pin.record_ids[0] ?? "")?.holding_verification);
  const wrap = document.createElement("div");
  wrap.className = "pin";
  if (open) {
    const card = document.createElement("div");
    card.className = "pin-card";
    card.setAttribute("role", "group");
    card.setAttribute("aria-label", `${inst.name}: ${pin.count} ${t("world.holding_other")}`);
    const title = document.createElement("p");
    title.className = "display";
    title.style.fontSize = "0.95rem";
    title.textContent = inst.name;
    card.appendChild(title);
    const meta = document.createElement("p");
    meta.style.color = "var(--ink-muted)";
    meta.style.fontSize = "0.72rem";
    meta.textContent = `${L.precision(inst.location_precision)} · ${pin.count} ${pin.count === 1 ? t("world.holding_one") : t("world.holding_other")}`;
    card.appendChild(meta);
    const list = document.createElement("ul");
    list.style.marginTop = "0.35rem";
    for (const rid of pin.record_ids.slice(0, 4)) {
      const r = recordsById.get(rid);
      if (!r) continue;
      const li = document.createElement("li");
      li.style.borderTop = "1px solid var(--rule)";
      li.style.padding = "0.25rem 0";
      const a = document.createElement("a");
      a.href = `#record-${r.id}`;
      a.textContent = r.title;
      a.style.textDecoration = "underline";
      a.style.display = "block";
      a.style.overflow = "hidden";
      a.style.textOverflow = "ellipsis";
      a.style.whiteSpace = "nowrap";
      li.appendChild(a);
      if (r.call_number) {
        const cn = document.createElement("span");
        cn.className = "tnum";
        cn.style.color = "var(--ink-muted)";
        cn.style.fontSize = "0.72rem";
        cn.textContent = t("common.callNoCap", { n: r.call_number });
        li.appendChild(cn);
      }
      list.appendChild(li);
    }
    card.appendChild(list);
    if (pin.record_ids.length > 4) {
      const more = document.createElement("p");
      more.style.fontSize = "0.72rem";
      more.style.color = "var(--ink-muted)";
      more.textContent = t("world.moreInList", { n: pin.record_ids.length - 4 });
      card.appendChild(more);
    }
    const link = document.createElement("a");
    link.href = href(`/institutions/${inst.slug}`);
    link.textContent = t("common.visitRequest");
    link.style.display = "inline-block";
    link.style.marginTop = "0.35rem";
    link.style.color = "var(--teal-deep)";
    link.style.textDecoration = "underline";
    card.appendChild(link);
    wrap.appendChild(card);
    const stem = document.createElement("div");
    stem.className = "pin-stem";
    wrap.appendChild(stem);
  }
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "pin-button";
  btn.setAttribute("aria-label", `${inst.name}, ${tn("world.holding", pin.count)}, ${L.precision(inst.location_precision)}`);
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  const dot = document.createElement("span");
  dot.className = "pin-dot";
  dot.dataset.precision = kind;
  btn.appendChild(dot);
  if (!open) {
    const label = document.createElement("span");
    label.className = "pin-label";
    label.textContent = `${inst.name.length > 28 ? inst.name.slice(0, 26) + "…" : inst.name} · ${pin.count}`;
    btn.appendChild(label);
  }
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    onSelect();
  });
  wrap.appendChild(btn);
  return wrap;
}

export default function AtlasMap({ pins, recordsById }: Props) {
  const { t, tn, locale } = useT();
  const L = useLabels();
  const href = (h: string) => (locale === "fr" ? `/fr${h}` : h);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const { selectedInstitutionId, selectInstitution, focusInstitutionIds, selectedRecordId } = useSelection();

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [-63.6, 44.9],
      zoom: 5.4,
      attributionControl: false,
      cooperativeGestures: false,
    });
    map.addControl(new maplibregl.AttributionControl({ compact: false, customAttribution: ATTRIBUTION }), "bottom-left");
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
    map.on("load", () => setReady(true));
    map.on("click", () => selectInstitution(null));
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    for (const pin of pins) {
      const inst = pin.institution;
      if (inst.latitude == null || inst.longitude == null) continue;
      const open = selectedInstitutionId === inst.id;
      const el = buildMarkerEl(pin, recordsById, open, () => selectInstitution(open ? null : inst.id), L, t, tn, href);
      const marker = new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat([inst.longitude, inst.latitude]).addTo(map);
      markersRef.current.push(marker);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pins, recordsById, ready, selectedInstitutionId, selectInstitution, locale]);

  // fit to pins when the result set changes
  const pinKey = pins.map((p) => p.institution.id).join("|");
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const coords = pins.filter((p) => p.institution.latitude != null && p.institution.longitude != null).map((p) => [p.institution.longitude as number, p.institution.latitude as number] as [number, number]);
    if (coords.length === 0) return;
    const reduce = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (coords.length === 1) {
      map.easeTo({ center: coords[0], zoom: 9, duration: reduce ? 0 : 500 });
      return;
    }
    const b = coords.reduce((bb, c) => bb.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
    map.fitBounds(b, { padding: { top: 60, bottom: 60, left: 60, right: 60 }, maxZoom: 10, duration: reduce ? 0 : 600 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pinKey, ready]);

  // guide focus / record selection → pan to institution
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const target = selectedInstitutionId ?? focusInstitutionIds[0];
    if (!target) return;
    const pin = pins.find((p) => p.institution.id === target);
    if (!pin || pin.institution.latitude == null || pin.institution.longitude == null) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.easeTo({ center: [pin.institution.longitude, pin.institution.latitude], zoom: Math.max(map.getZoom(), 7), duration: reduce ? 0 : 500, offset: [0, 150] });
  }, [selectedInstitutionId, focusInstitutionIds, selectedRecordId, pins, ready]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="atlas-map" role="region" aria-label={t("world.region")} />
      <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-2 text-[11px]">
        <span className="pointer-events-auto flex items-center gap-1 border border-rule bg-paper/90 px-2 py-0.5"><span className="pin-dot" style={{ width: 10, height: 10 }} /> {t("world.legend.verified")}</span>
        <span className="pointer-events-auto flex items-center gap-1 border border-rule bg-paper/90 px-2 py-0.5"><span className="pin-dot" data-precision="catalogue" style={{ width: 10, height: 10 }} /> {t("world.legend.catalogue")}</span>
        <span className="pointer-events-auto flex items-center gap-1 border border-rule bg-paper/90 px-2 py-0.5"><span className="pin-dot" data-precision="approximate" style={{ width: 10, height: 10 }} /> {t("world.legend.approximate")}</span>
        <span className="pointer-events-auto flex items-center gap-1 border border-rule bg-paper/90 px-2 py-0.5"><span className="pin-dot" data-precision="demo" style={{ width: 10, height: 10 }} /> {t("world.legend.demo")}</span>
      </div>
    </div>
  );
}
