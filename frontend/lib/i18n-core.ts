/**
 * Locale plumbing shared by server and client code (no React here).
 *
 * The UI locale lives in the URL: `/fr/...` is French, anything else English. `proxy.ts` rewrites `/fr/x` to the
 * `/x` route and passes the locale as the `x-locale` request header; it also remembers the choice in a cookie and
 * sends a returning French reader from `/` to `/fr`. Strings live in `messages/{en,fr}.json`.
 */
export type Locale = "en" | "fr";
export const LOCALES: readonly Locale[] = ["en", "fr"] as const;
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "bhdh_locale";
export const LOCALE_HEADER = "x-locale";
/** BCP-47 tags used for dates, numbers and speech (Canadian English / Canadian French). */
export const BCP47: Record<Locale, string> = { en: "en-CA", fr: "fr-CA" };
export const LOCALE_NAME: Record<Locale, string> = { en: "English", fr: "Français" };

export type Messages = Record<string, unknown>;
export type Vars = Record<string, string | number | null | undefined>;

export function isLocale(v: unknown): v is Locale {
  return v === "en" || v === "fr";
}

export function lookup(messages: Messages, key: string): unknown {
  let cur: unknown = messages;
  for (const part of key.split(".")) {
    if (cur && typeof cur === "object" && part in (cur as Record<string, unknown>)) cur = (cur as Record<string, unknown>)[part];
    else return undefined;
  }
  return cur;
}

export function interpolate(s: string, vars?: Vars): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (vars[k] === undefined || vars[k] === null ? m : String(vars[k])));
}

export interface Translator {
  locale: Locale;
  /** A string by dot-path key, with `{var}` interpolation. Missing keys return the key itself (visible, never silent). */
  t: (key: string, vars?: Vars) => string;
  /** Plural: picks `key_one` when n === 1, else `key_other`, and interpolates `{n}` (formatted for the locale). */
  tn: (key: string, n: number, vars?: Vars) => string;
  /** Raw value (arrays / objects such as the home-page stories). */
  raw: <T = unknown>(key: string) => T;
  /** Enum label helper: `label("status", "in_review")` → "in review"; falls back to the raw value. */
  label: (group: string, value: string | null | undefined) => string;
}

export function makeT(messages: Messages, locale: Locale): Translator {
  const nf = new Intl.NumberFormat(BCP47[locale]);
  const t = (key: string, vars?: Vars) => {
    const v = lookup(messages, key);
    return typeof v === "string" ? interpolate(v, vars) : key;
  };
  return {
    locale,
    t,
    tn: (key, n, vars) => t(n === 1 ? `${key}_one` : `${key}_other`, { ...vars, n: nf.format(n) }),
    raw: <T,>(key: string) => lookup(messages, key) as T,
    label: (group, value) => {
      if (value == null || value === "") return "";
      const v = lookup(messages, `${group}.${value}`);
      return typeof v === "string" ? v : value;
    },
  };
}

/** Prefix an internal href for the locale. API, asset and external links are left alone. */
export function localePath(locale: Locale, href: string): string {
  if (locale === "en") return href;
  if (!href.startsWith("/") || href.startsWith("/api") || href.startsWith("/openapi") || /\.[a-z0-9]+(\?|$)/i.test(href.split("?")[0])) return href;
  if (/^\/(en|fr)(\/|\?|#|$)/.test(href)) return href;
  if (href === "/") return `/${locale}`;
  if (href.startsWith("/?") || href.startsWith("/#")) return `/${locale}${href.slice(1)}`;
  return `/${locale}${href}`;
}

/** `/fr/search` → `/search`; `/fr` → `/`; `/search` unchanged. */
export function stripLocale(pathname: string): string {
  const m = pathname.match(/^\/(en|fr)(\/.*)?$/);
  return m ? m[2] || "/" : pathname;
}

export function localeFromPathname(pathname: string): Locale | null {
  const m = pathname.match(/^\/(en|fr)(\/|$)/);
  return m ? (m[1] as Locale) : null;
}

/** Same page in another language: `/fr/institutions?x=1` → `/en/institutions?x=1` (the `/en` prefix is a redirect that sets the cookie). */
export function switchLocalePath(pathname: string, search: string, target: Locale): string {
  const base = stripLocale(pathname);
  return `/${target}${base === "/" ? "" : base}${search}`;
}

export function formatDateTime(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(BCP47[locale], { dateStyle: "medium", timeStyle: "short" });
}

export function formatDate(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(BCP47[locale], { dateStyle: "medium" });
}

export function formatNumber(n: number, locale: Locale): string {
  return new Intl.NumberFormat(BCP47[locale]).format(n);
}

const FR_WORDS = new Set(["le", "la", "les", "des", "une", "est", "et", "du", "dans", "pour", "avec", "sur", "qui", "que", "pas", "sont", "aux", "cette", "ses", "par", "ont", "été", "plus", "ou", "où", "fonds", "musée", "bibliothèque", "archives", "histoire", "noirs", "communauté", "collection", "documents"]);
const EN_WORDS = new Set(["the", "and", "of", "to", "in", "is", "for", "with", "that", "this", "are", "from", "by", "on", "it", "as", "its", "was", "were", "has", "have", "their", "which", "museum", "library", "history", "black", "community", "records", "holds", "collection"]);

/**
 * Deterministic guess at the language of a short text (institution descriptions) from function words.
 * Returns null when there is no clear signal, so the UI shows no badge rather than a wrong one.
 */
export function detectLanguage(text: string | null | undefined): Locale | null {
  if (!text) return null;
  const words = text.toLowerCase().match(/[a-zàâçéèêëîïôûùüÿœ']+/g) ?? [];
  let fr = 0;
  let en = 0;
  for (const w of words) {
    if (FR_WORDS.has(w)) fr++;
    if (EN_WORDS.has(w)) en++;
  }
  if (fr + en < 3) return null;
  if (fr >= en * 2) return "fr";
  if (en >= fr * 2) return "en";
  return null;
}
