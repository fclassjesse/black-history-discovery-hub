"use client";

import { useWorld } from "@/lib/worldStore";
import { worldHandle } from "@/components/world/worldHandle";
import { useT } from "@/lib/i18n";

function Icon({ d }: { d: string }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>;
}

/** Pill controls for the world: zoom, recentre, globe ⇄ flat. Styled in the design language instead of MapLibre's defaults. */
export function WorldControls({ className = "" }: { className?: string }) {
  const { t } = useT();
  const { projection, setProjection, webgl } = useWorld();
  if (webgl === false) return null;
  const map = () => worldHandle.map;
  return (
    <div className={`world-controls ${className}`} role="group" aria-label={t("world.controls")}>
      <button type="button" className="btn btn-secondary btn-icon" aria-label={t("world.zoomIn")} onClick={() => map()?.zoomIn({ duration: 400 })}><Icon d="M12 5v14M5 12h14" /></button>
      <button type="button" className="btn btn-secondary btn-icon" aria-label={t("world.zoomOut")} onClick={() => map()?.zoomOut({ duration: 400 })}><Icon d="M5 12h14" /></button>
      <button type="button" className="btn btn-secondary btn-icon" aria-label={t("world.recentre")} onClick={() => worldHandle.reset?.()}><Icon d="M12 3v3M12 18v3M3 12h3M18 12h3M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z" /></button>
      <button type="button" className="btn btn-secondary btn-sm" aria-pressed={projection === "flat"} onClick={() => setProjection(projection === "globe" ? "flat" : "globe")} title={t("world.switchTitle")}>
        {projection === "globe" ? t("world.flat") : t("world.globe")}
      </button>
    </div>
  );
}
