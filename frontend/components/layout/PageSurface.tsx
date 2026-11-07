"use client";

import { useEffect } from "react";

/** Sets the page's base colour on <html> so overscroll and the area behind fixed layers match. */
export function PageSurface({ tone }: { tone: "flame" | "chalk" }) {
  useEffect(() => {
    document.documentElement.dataset.surface = tone;
    return () => { delete document.documentElement.dataset.surface; };
  }, [tone]);
  return null;
}
