"use client";

import { useSyncExternalStore } from "react";

/**
 * Live media-query match. The server snapshot assumes a desktop so SSR markup matches the common case; a phone
 * re-renders once after hydration (the desktop branch is also hidden by CSS below `lg`, so nothing flashes).
 */
export function useMediaQuery(query: string, serverDefault = true): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => serverDefault,
  );
}

/** Tailwind's `lg` breakpoint: the results drawer floats beside the world from here up. */
export const DESKTOP_QUERY = "(min-width: 1024px)";
