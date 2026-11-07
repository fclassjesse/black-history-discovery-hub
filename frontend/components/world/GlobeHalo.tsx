"use client";

import { useEffect, useRef } from "react";
import type { Map as MLMap } from "maplibre-gl";
import { useWorld } from "@/lib/worldStore";
import { prefersReducedMotion } from "@/lib/motion";

/** Orbit geometry relative to the sphere radius: a wide, flat ellipse tilted a little, like a ring seen from above. */
const ORBIT_A = 1.2;
const ORBIT_B = 0.34;
const ORBIT_TILT_DEG = -14;
const ORBIT_PERIOD_S = 34;
const ARC_POINTS = 56;

const PLANE_PATH = "M2 18 L40 4 L30 28 L22 19 Z";

function arcPoints(a: number, b: number, from: number, to: number): string {
  const pts: string[] = [];
  for (let i = 0; i <= ARC_POINTS; i++) {
    const t = from + ((to - from) * i) / ARC_POINTS;
    pts.push(`${(a * Math.cos(t)).toFixed(1)},${(b * Math.sin(t)).toFixed(1)}`);
  }
  return pts.join(" ");
}

/**
 * Cartoon dressing that makes the sphere read as a ball, not a disc:
 *  - a shading layer (dark toward the rim, a soft sheen top-left),
 *  - a thick ink rim with an offset paper shadow,
 *  - a tilted elliptical orbit whose far half is drawn *behind* the globe (the map canvas is transparent outside the
 *    sphere, so a z-index −1 layer shows through around it) and whose near half passes in front, with a paper plane
 *    that shrinks as it flies round the back,
 *  - three clouds hugging the rim and two sparks.
 * It measures the sphere's on-screen circle from the map itself (centre = projected map centre, radius = a point
 * 85° east, which is where the horizon sits with MapLibre's camera), so it follows the spin and any resize. Hidden
 * while the globe is tilted, zoomed in, flat, or bigger than the viewport.
 */
export function GlobeHalo({ map }: { map: MLMap }) {
  const frontRef = useRef<HTMLDivElement>(null);
  const backRef = useRef<HTMLDivElement>(null);
  const orbitFrontRef = useRef<SVGGElement>(null);
  const orbitBackRef = useRef<SVGGElement>(null);
  const arcFrontRef = useRef<SVGPolylineElement>(null);
  const arcBackRef = useRef<SVGPolylineElement>(null);
  const planeFrontRef = useRef<SVGGElement>(null);
  const planeBackRef = useRef<SVGGElement>(null);
  const geomRef = useRef({ gx: 0, gy: 0, r: 0, show: false });
  const { mode, projection } = useWorld();

  // measure the sphere and place everything
  useEffect(() => {
    const front = frontRef.current;
    const back = backRef.current;
    if (!front || !back) return;
    let raf = 0;
    const measure = () => {
      raf = 0;
      const w = map.getContainer().clientWidth;
      const h = map.getContainer().clientHeight;
      const usable = projection === "globe" && mode === "idle" && Math.abs(map.getPitch()) < 1 && Math.abs(map.getBearing()) < 1;
      const hide = () => { front.dataset.show = "false"; back.dataset.show = "false"; geomRef.current.show = false; };
      if (!usable) { hide(); return; }
      const c = map.getCenter();
      const cp = map.project(c);
      const edge = map.project([c.lng + 85, c.lat]);
      const r = Math.hypot(edge.x - cp.x, edge.y - cp.y) / Math.sin((85 * Math.PI) / 180);
      if (!Number.isFinite(r) || r < 60 || r > Math.min(w, h) * 0.75) { hide(); return; }
      geomRef.current = { gx: cp.x, gy: cp.y, r, show: true };
      for (const el of [front, back]) {
        el.dataset.show = "true";
        el.style.setProperty("--gx", `${cp.x.toFixed(1)}px`);
        el.style.setProperty("--gy", `${cp.y.toFixed(1)}px`);
        el.style.setProperty("--gr", `${r.toFixed(1)}px`);
      }
      const a = r * ORBIT_A;
      const b = r * ORBIT_B;
      const place = `translate(${cp.x.toFixed(1)} ${cp.y.toFixed(1)}) rotate(${ORBIT_TILT_DEG})`;
      orbitFrontRef.current?.setAttribute("transform", place);
      orbitBackRef.current?.setAttribute("transform", place);
      arcFrontRef.current?.setAttribute("points", arcPoints(a, b, 0, Math.PI));
      arcBackRef.current?.setAttribute("points", arcPoints(a, b, Math.PI, 2 * Math.PI));
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };
    schedule();
    map.on("move", schedule);
    map.on("resize", schedule);
    map.on("idle", schedule);
    return () => { map.off("move", schedule); map.off("resize", schedule); map.off("idle", schedule); if (raf) cancelAnimationFrame(raf); };
  }, [map, mode, projection]);

  // fly the paper plane round the orbit: in front on the near half, behind the sphere on the far half
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let raf = 0;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const g = geomRef.current;
      const pf = planeFrontRef.current;
      const pb = planeBackRef.current;
      if (!g.show || !pf || !pb || document.visibilityState !== "visible") return;
      const theta = ((now / 1000) / ORBIT_PERIOD_S) * Math.PI * 2;
      const a = g.r * ORBIT_A;
      const b = g.r * ORBIT_B;
      const x = a * Math.cos(theta);
      const y = b * Math.sin(theta);
      const heading = (Math.atan2(b * Math.cos(theta), -a * Math.sin(theta)) * 180) / Math.PI + 20;
      const depth = (Math.sin(theta) + 1) / 2; // 1 = nearest (bottom of the ellipse)
      const scale = 0.6 + 0.5 * depth;
      const t = `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${heading.toFixed(1)}) scale(${scale.toFixed(2)}) translate(-22 -16)`;
      const inFront = Math.sin(theta) >= 0;
      pf.setAttribute("transform", t); pb.setAttribute("transform", t);
      pf.setAttribute("opacity", inFront ? "1" : "0");
      pb.setAttribute("opacity", inFront ? "0" : "1");
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const plane = (ref: React.RefObject<SVGGElement | null>) => (
    <g ref={ref} className="globe-plane">
      <path d={PLANE_PATH} fill="var(--cream)" stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M22 19 L40 4" fill="none" stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M22 19 L20 29" fill="none" stroke="var(--ink)" strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );

  return (
    <>
      {/* behind the sphere */}
      <div ref={backRef} className="globe-halo globe-halo-back" data-show="false" aria-hidden>
        <div className="globe-drop" />
        <svg className="globe-orbit-svg">
          <g ref={orbitBackRef}>
            <polyline ref={arcBackRef} className="globe-orbit-arc globe-orbit-arc-back" />
            {plane(planeBackRef)}
          </g>
        </svg>
      </div>
      {/* in front of the sphere, under the pins */}
      <div ref={frontRef} className="globe-halo" data-show="false" aria-hidden>
        <div className="globe-shade" />
        <div className="globe-rim" />
        <svg className="globe-orbit-svg">
          <g ref={orbitFrontRef}>
            <polyline ref={arcFrontRef} className="globe-orbit-arc" />
            {plane(planeFrontRef)}
          </g>
        </svg>
        {[0, 1, 2].map((i) => (
          <div key={i} className="globe-cloud-track" data-i={i}>
            <svg className="globe-cloud" viewBox="0 0 120 56" width="120" height="56">
              <path d="M22 44 a16 16 0 0 1 4 -31 a20 20 0 0 1 38 -4 a17 17 0 0 1 30 10 a14 14 0 0 1 2 25 Z" fill="var(--white)" stroke="var(--ink)" strokeWidth="3" strokeLinejoin="round" />
              <path d="M34 40 h40" stroke="var(--chalk-2)" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </div>
        ))}
        <svg className="globe-spark globe-spark-a" viewBox="0 0 24 24" width="22" height="22"><path d="M12 1 l3 8 l8 3 l-8 3 l-3 8 l-3 -8 l-8 -3 l8 -3 z" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" /></svg>
        <svg className="globe-spark globe-spark-b" viewBox="0 0 24 24" width="16" height="16"><path d="M12 1 l3 8 l8 3 l-8 3 l-3 8 l-3 -8 l-8 -3 l8 -3 z" fill="var(--rose)" stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" /></svg>
      </div>
    </>
  );
}
