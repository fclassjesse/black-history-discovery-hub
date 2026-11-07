import type { Map as MLMap } from "maplibre-gl";

/** Imperative handle to the single world map, for controls rendered elsewhere. */
export const worldHandle: { map: MLMap | null; reset: (() => void) | null } = { map: null, reset: null };
