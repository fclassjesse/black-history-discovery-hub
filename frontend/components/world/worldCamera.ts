import { LngLatBounds, type EaseToOptions, type Map as MLMap, type PaddingOptions } from "maplibre-gl";
import type { Locality, Pin } from "@/lib/types";

const NO_PADDING: PaddingOptions = { left: 0, right: 0, top: 0, bottom: 0 };

/**
 * fitBounds that works from any starting layout. MapLibre adds `padding` on top of the map's persistent padding, and
 * the stage composition keeps a large one (the globe sits in the right half: ~48% of the width on desktop, 70% of the
 * height on phones). Stage + results padding is wider than the screen, so fitBounds warned "cannot fit" and did
 * nothing: the camera stood still until the guide's focus moved it seconds later. Here the target is computed with the
 * persistent padding cleared, then the camera eases there while that padding animates to zero, so the globe glides
 * from the stage composition into the results frame in one move. Returns false when no camera fits.
 */
export function easeToBounds(map: MLMap, coords: [number, number][], padding: PaddingOptions, maxZoom: number, ease: Omit<EaseToOptions, "center" | "zoom" | "padding">): boolean {
  const bounds = coords.reduce((b, c) => b.extend(c), new LngLatBounds(coords[0], coords[0]));
  const saved = map.getPadding();
  // no frame renders between these two calls, so the temporary padding is never seen
  map.setPadding(NO_PADDING);
  const cam = map.cameraForBounds(bounds, { padding, maxZoom });
  map.setPadding(saved);
  if (!cam?.center || cam.zoom == null) return false;
  map.easeTo({ ...ease, center: cam.center, zoom: cam.zoom, padding: NO_PADDING });
  return true;
}

/** Pins further than this from the main holder are left out of the arrival fit (they stay on the map). Halifax ↔
 *  Washington is ~1,300 km, so Atlantic Canada + the US east coast frame together; London does not drag the camera
 *  back out to a whole-ocean view. */
const CLUSTER_KM = 1600;
const EARTH_KM = 6371;

type LngLat = [number, number];

function km(a: LngLat, b: LngLat): number {
  const rad = Math.PI / 180;
  const dLat = (b[1] - a[1]) * rad;
  const dLng = (b[0] - a[0]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * Where the camera should land when results arrive: the holder with the most matching records and the holders near
 * it. Fitting every pin made a result set with one far-away holder frame the whole ocean, which is about the zoom the
 * globe already has, so the camera did not visibly move until the guide's focus arrived seconds later.
 */
export function arrivalCoords(pins: Pin[], locality?: Locality | null): LngLat[] {
  const located = pins.filter((p) => p.institution.latitude != null && p.institution.longitude != null);
  if (locality) {
    // the asker said where they are: frame their region's holders, or the region itself when none hold a match
    const [west, south, east, north] = locality.bbox;
    const inside = located
      .map((p): LngLat => [p.institution.longitude as number, p.institution.latitude as number])
      .filter(([lng, lat]) => lng >= west && lng <= east && lat >= south && lat <= north);
    return inside.length > 1 ? inside : [[west, south], [east, north]];
  }
  if (located.length === 0) return [];
  const anchor = located.reduce((best, p) => (p.count > best.count ? p : best), located[0]);
  const at = (p: Pin): LngLat => [p.institution.longitude as number, p.institution.latitude as number];
  const origin = at(anchor);
  return located.map(at).filter((c) => km(origin, c) <= CLUSTER_KM);
}
