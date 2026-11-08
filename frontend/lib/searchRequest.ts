import { apiGetShared, qs } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

const PAGE_SIZE = 20;
const LIST_KEYS = ["types", "access", "institution", "lang", "verification", "rights", "country", "people", "places", "communities"] as const;
const PASS_KEYS = ["date_from", "date_to", "identifier", "location", "source"] as const;

/** The /api/search URL for a results-page query string. One builder for the results view and the ask-time prefetch,
 *  so both produce the same key and share one request. */
export function searchPath(sp: URLSearchParams, locale: string): string {
  const mode = sp.get("mode") === "advanced" ? "advanced" : "natural";
  const params: Record<string, string | number> = { q: sp.get("q") ?? "", mode, page: Number(sp.get("page") ?? "1") || 1, page_size: PAGE_SIZE, locale };
  for (const k of LIST_KEYS) params[k] = (sp.get(k) ?? "").split(",").filter(Boolean).join(",");
  for (const k of PASS_KEYS) params[k] = sp.get(k) ?? "";
  return `/api/search${qs(params)}`;
}

/** Starts (or joins) the search for a results URL such as "/fr?q=…"; the results view picks the same request up. */
export function prefetchSearch(url: string, locale: string): void {
  const query = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
  apiGetShared<SearchResponse>(searchPath(new URLSearchParams(query), locale)).catch(() => { /* the results view reports errors */ });
}
