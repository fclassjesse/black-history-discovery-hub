"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { InstitutionCard, Pin } from "@/lib/types";

let cache: InstitutionCard[] | null = null;
let inflight: Promise<InstitutionCard[]> | null = null;

function load(): Promise<InstitutionCard[]> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = apiGet<{ institutions: InstitutionCard[] }>("/api/institutions").then((d) => { cache = d.institutions; return cache; }).finally(() => { inflight = null; });
  }
  return inflight;
}

/** Shared, de-duplicated institutions directory (several home sections need it). */
export function useInstitutions() {
  const [items, setItems] = useState<InstitutionCard[] | null>(cache);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    load().then((d) => { if (alive) setItems(d); }).catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, []);
  return { items, error };
}

/** Directory entries as world pins (count = published records). */
export function institutionsToPins(items: InstitutionCard[]): Pin[] {
  return items.filter((i) => i.latitude != null && i.longitude != null).map((i) => ({ institution: i, record_ids: [], count: i.published_records ?? 0 }));
}
