"use client";

import type { AccessType, HoldingVerification, LocationPrecision, ReviewStatus } from "@/lib/types";
import { useLabels } from "@/lib/labels";

export function AccessBadge({ access }: { access: AccessType }) {
  const L = useLabels();
  const cls = access === "online" ? "badge-online" : access === "physical" ? "badge-physical" : access === "both" ? "badge-online" : "";
  return <span className={`badge ${cls}`}>{L.access(access)}</span>;
}

export function VerificationBadge({ verification }: { verification: HoldingVerification }) {
  const L = useLabels();
  const cls = verification === "verified_partner" ? "badge-verified" : verification === "demo" ? "badge-demo" : verification === "online_item" ? "badge-online" : "";
  return <span className={`badge ${cls}`} title={L.verification(verification)}>{L.verification(verification)}</span>;
}

export function PrecisionBadge({ precision }: { precision: LocationPrecision }) {
  const L = useLabels();
  const cls = precision === "demo" ? "badge-demo" : precision === "partner_verified" ? "badge-verified" : "";
  return <span className={`badge ${cls}`}>{L.precision(precision)}</span>;
}

export function StatusBadge({ status }: { status: ReviewStatus }) {
  const L = useLabels();
  const cls = status === "published" ? "badge-ok" : status === "withdrawn" ? "badge-danger" : status === "in_review" ? "badge-online" : "";
  return <span className={`badge ${cls}`}>{L.status(status)}</span>;
}
