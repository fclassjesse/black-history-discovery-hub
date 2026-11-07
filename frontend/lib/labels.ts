import type { HoldingVerification, LocationPrecision } from "@/lib/types";
import { useT } from "@/lib/i18n";

/** Resource-type codes in display order; labels come from messages (`resourceType.*`). */
export const RESOURCE_TYPE_CODES = ["book", "serial", "manuscript", "archival_collection", "image", "map", "audio", "video", "dataset", "finding_aid", "artifact", "other"] as const;

/**
 * Translated enum labels for badges, facets and forms.
 * `const L = useLabels(); L.verification("catalogue_record")` → "Catalogue record" / "Notice de catalogue".
 */
export function useLabels() {
  const { label, t } = useT();
  return {
    verification: (v: string | null | undefined) => label("verification", v),
    precision: (v: string | null | undefined) => label("precision", v),
    access: (v: string | null | undefined) => label("access", v),
    status: (v: string | null | undefined) => label("status", v),
    rights: (v: string | null | undefined) => label("rights", v) || (v ?? "").replace("_", " "),
    kind: (v: string | null | undefined) => label("kind", v) || (v ?? "").replace("_", " "),
    language: (code: string | null | undefined) => label("languageName", code),
    resourceType: (v: string | null | undefined) => label("resourceType", v) || (v ?? "").replace("_", " "),
    resourceTypes: RESOURCE_TYPE_CODES.map((code) => [code, t(`resourceType.${code}`)] as const),
    role: (v: string | null | undefined) => label("partner.roles", v),
  };
}

export function pinKind(precision: LocationPrecision, verification?: HoldingVerification | null): "verified" | "catalogue" | "demo" | "approximate" {
  if (precision === "demo") return "demo";
  if (precision === "partner_verified") return "verified";
  if (verification === "catalogue_record" || precision === "building") return "catalogue";
  return "approximate";
}
