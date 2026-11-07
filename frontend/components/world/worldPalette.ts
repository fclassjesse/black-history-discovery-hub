import type { Map as MLMap } from "maplibre-gl";

/**
 * Re-paints the OpenFreeMap "positron" style into the Paper Atlas globe:
 * a cream-paper sea, moss-green continents with a halftone grain, ink
 * roads and borders. Against the vermilion page the sphere reads as a
 * bright paper sticker, not a hole in the background.
 */
export const SEA = "#f6ecd8";
export const SEA_DEEP = "#efe1c6";
export const LAND = "#4f9a63";
export const LAND_2 = "#6bb07a";
export const LAND_3 = "#3f864f";
export const INK = "#1b1715";

const HALFTONE_ID = "paper-atlas-land";

/** A tiny tile: land green with one darker dot, so continents carry the same halftone as the plates. */
function halftoneTile(): { width: number; height: number; data: Uint8Array } {
  const size = 10;
  const data = new Uint8Array(size * size * 4);
  const base = [0x4f, 0x9a, 0x63];
  const dot = [0x3f, 0x86, 0x4f];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const isDot = (x === 2 || x === 3) && (y === 2 || y === 3);
      const isDot2 = (x === 7 || x === 8) && (y === 7 || y === 8);
      const c = isDot || isDot2 ? dot : base;
      data[i] = c[0]; data[i + 1] = c[1]; data[i + 2] = c[2]; data[i + 3] = 255;
    }
  }
  return { width: size, height: size, data };
}

export function applyPaperAtlas(map: MLMap) {
  const style = map.getStyle();
  if (!style?.layers) return;
  try { if (!map.hasImage(HALFTONE_ID)) map.addImage(HALFTONE_ID, halftoneTile(), { pixelRatio: 1 }); } catch { /* pattern is decoration only */ }
  for (const layer of style.layers) {
    const id = layer.id;
    const sl = "source-layer" in layer ? layer["source-layer"] : undefined;
    try {
      if (layer.type === "background") {
        map.setPaintProperty(id, "background-color", LAND);
        if (map.hasImage(HALFTONE_ID)) map.setPaintProperty(id, "background-pattern", HALFTONE_ID);
      } else if (layer.type === "fill") {
        if (sl === "water") { map.setPaintProperty(id, "fill-color", SEA); map.setPaintProperty(id, "fill-opacity", 1); }
        else if (sl === "park" || id.includes("wood")) { map.setPaintProperty(id, "fill-color", LAND_2); map.setPaintProperty(id, "fill-opacity", 0.9); }
        else if (sl === "building") { map.setPaintProperty(id, "fill-color", LAND_3); map.setPaintProperty(id, "fill-outline-color", "rgba(27,23,21,0.3)"); }
        else if (sl === "landuse") { map.setPaintProperty(id, "fill-color", LAND_2); map.setPaintProperty(id, "fill-opacity", 0.6); }
        else if (sl === "landcover") { map.setPaintProperty(id, "fill-color", LAND_2); map.setPaintProperty(id, "fill-opacity", 0.7); }
        else if (sl === "aeroway" || sl === "transportation") { map.setPaintProperty(id, "fill-color", LAND_3); }
      } else if (layer.type === "line") {
        if (sl === "waterway") { map.setPaintProperty(id, "line-color", SEA); }
        else if (sl === "boundary") { map.setPaintProperty(id, "line-color", INK); map.setPaintProperty(id, "line-opacity", id === "boundary_2" ? 0.6 : 0.32); }
        else if (sl === "transportation") {
          const major = id.includes("motorway") || id.includes("major");
          map.setPaintProperty(id, "line-color", id.includes("casing") ? LAND : INK);
          if (!id.includes("casing")) map.setPaintProperty(id, "line-opacity", major ? 0.5 : 0.25);
        } else if (sl === "aeroway") { map.setPaintProperty(id, "line-color", LAND_3); }
      } else if (layer.type === "symbol") {
        const onWater = sl === "water_name" || sl === "waterway";
        map.setPaintProperty(id, "text-color", INK);
        map.setPaintProperty(id, "text-halo-color", onWater ? SEA : "#e9f3e9");
        map.setPaintProperty(id, "text-halo-width", onWater ? 1.2 : 1.5);
        if (id.startsWith("label_country")) { map.setLayoutProperty(id, "text-transform", "uppercase"); map.setLayoutProperty(id, "text-letter-spacing", 0.18); }
      }
    } catch {
      /* a layer without that property: ignore */
    }
  }
}
