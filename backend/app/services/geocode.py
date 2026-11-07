"""Nominatim geocoding (OpenStreetMap). 1 req/s, identifying User-Agent, cached on disk.
Precision labels are stored with the coordinates so the UI never over-claims.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.http import get_http

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
SOURCE = "nominatim"
PRECISION_FROM_OSM = {
    "building": "building", "amenity": "building", "tourism": "building", "office": "building", "shop": "building",
    "historic": "building", "leisure": "building", "highway": "road", "place": "locality", "boundary": "locality",
}


async def geocode(query: str) -> dict[str, Any] | None:
    res = await get_http().get(NOMINATIM_URL, {"q": query, "format": "jsonv2", "limit": "1", "addressdetails": "1"}, source=SOURCE, min_interval=1.1)
    if not res.ok:
        return None
    hits = res.json()
    if not hits:
        return None
    h = hits[0]
    cls = h.get("category") or h.get("class") or ""
    precision = PRECISION_FROM_OSM.get(cls, "locality")
    if cls == "building" or (h.get("osm_type") in ("node", "way") and cls in ("amenity", "tourism", "office", "historic", "leisure")):
        precision = "building"
    return {
        "latitude": float(h["lat"]),
        "longitude": float(h["lon"]),
        "precision": precision,
        "display_name": h.get("display_name"),
        "osm": f"{h.get('osm_type')}/{h.get('osm_id')}",
        "source": f"Nominatim (OpenStreetMap) query '{query}' on {datetime.now(timezone.utc).date().isoformat()} → {h.get('display_name')}",
    }
