"""Rights classification from explicit signals only. Unknown stays unknown."""
from __future__ import annotations

PUBLIC_DOMAIN_MARKERS = ("publicdomain/mark", "publicdomain/zero", "public domain", "not_in_copyright", "no known copyright")


def classify(
    *,
    license_url: str | None = None,
    rights_text: str | None = None,
    copyright_status: str | None = None,
    restricted: bool = False,
) -> tuple[str, str | None]:
    """Returns (rights_status, human rights label)."""
    lic = (license_url or "").lower()
    txt = (rights_text or "").lower()
    cps = (copyright_status or "").lower()
    if any(m in lic for m in PUBLIC_DOMAIN_MARKERS) or any(m in txt for m in PUBLIC_DOMAIN_MARKERS) or cps == "not_in_copyright":
        return "public_domain", rights_text or license_url or "Public domain (as stated by the source)"
    if "creativecommons.org/licenses" in lic or txt.startswith("cc "):
        return "cc", rights_text or license_url
    if restricted:
        return "in_copyright", rights_text or "Access-restricted digital item (lending); the source enforces its own terms."
    if "in copyright" in txt or cps in ("in_copyright", "copyrighted"):
        return "in_copyright", rights_text or "In copyright (as stated by the source)"
    return "unknown", rights_text or license_url


def full_text_permitted(rights_status: str, date_start: int | None, restricted: bool) -> bool:
    """We only index OCR/full text when the source signals open, permitted material."""
    if restricted:
        return False
    if rights_status in ("public_domain", "cc"):
        return True
    return bool(date_start and date_start < 1930)
