"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";
import { useWorld } from "@/lib/worldStore";
import { useRoutePathname, useT } from "@/lib/i18n";

const WorldGlobe = dynamic(() => import("@/components/world/WorldGlobe"), { ssr: false });
const WORLD_ROUTES = new Set(["/"]);

/**
 * The fixed world behind the page. It stays mounted across the home → search
 * transition so the camera glides instead of re-loading. Other routes unmount it.
 */
export function WorldStage() {
  const { t } = useT();
  const pathname = useRoutePathname(); // locale prefix stripped: /fr is the home page too
  const active = WORLD_ROUTES.has(pathname);
  const { webgl, setVisible } = useWorld();
  useEffect(() => {
    setVisible(active);
    // let clicks fall through the page onto the world; panels opt back in with .pointer-events-auto
    if (active) document.documentElement.dataset.world = "on"; else delete document.documentElement.dataset.world;
    return () => { delete document.documentElement.dataset.world; };
  }, [active, setVisible]);
  if (!active) return null;
  return (
    <div className="world-stage" data-visible={active} aria-hidden={!active}>
      {webgl === false ? (
        <div className="absolute inset-0 grid place-items-center p-6">
          <p className="plate max-w-sm p-5 text-sm">{t("world.noWebgl")}</p>
        </div>
      ) : (
        <WorldGlobe />
      )}
    </div>
  );
}
