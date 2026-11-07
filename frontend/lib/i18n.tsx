"use client";

import NextLink from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, forwardRef, useCallback, useContext, useMemo, type ComponentProps } from "react";
import { BCP47, DEFAULT_LOCALE, formatDate, formatDateTime, formatNumber, localePath, makeT, stripLocale, type Locale, type Messages, type Translator } from "@/lib/i18n-core";

export * from "@/lib/i18n-core";

interface LocaleCtx { locale: Locale; messages: Messages }
const Ctx = createContext<LocaleCtx>({ locale: DEFAULT_LOCALE, messages: {} });

/** Provided once by the root layout with the active locale's messages (the other language is not shipped). */
export function LocaleProvider({ locale, messages, children }: { locale: Locale; messages: Messages; children: React.ReactNode }) {
  const value = useMemo(() => ({ locale, messages }), [locale, messages]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLocale(): Locale {
  return useContext(Ctx).locale;
}

/** `const { t, tn, raw, label, locale } = useT();` */
export function useT(): Translator {
  const { locale, messages } = useContext(Ctx);
  return useMemo(() => makeT(messages, locale), [messages, locale]);
}

/** Prefix internal hrefs for the current locale: `href("/search?q=x")` → `/fr/search?q=x` in French. */
export function useHref(): (href: string) => string {
  const locale = useLocale();
  return useCallback((href: string) => localePath(locale, href), [locale]);
}

/** The route pathname without the locale prefix, for "am I on this page" checks. */
export function useRoutePathname(): string {
  return stripLocale(usePathname());
}

/** `router.push` that keeps the locale prefix. */
export function useLocaleRouter() {
  const router = useRouter();
  const href = useHref();
  return useMemo(() => ({ push: (to: string) => router.push(href(to)), replace: (to: string) => router.replace(href(to)) }), [router, href]);
}

/** Locale-aware formatting for dates and counts. */
export function useFormat() {
  const locale = useLocale();
  return useMemo(() => ({
    locale,
    bcp47: BCP47[locale],
    dateTime: (iso: string | null | undefined) => formatDateTime(iso, locale),
    date: (iso: string | null | undefined) => formatDate(iso, locale),
    number: (n: number) => formatNumber(n, locale),
  }), [locale]);
}

type LinkProps = Omit<ComponentProps<typeof NextLink>, "href"> & { href: string };

/** Drop-in for next/link that prefixes internal hrefs with the active locale. */
export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function LocaleLink({ href, ...rest }, ref) {
  const locale = useLocale();
  return <NextLink ref={ref} href={localePath(locale, href)} {...rest} />;
});

/** Current search string (`?a=b`) or empty, for building the language-switch link. */
export function useSearchString(): string {
  const sp = useSearchParams();
  const s = sp.toString();
  return s ? `?${s}` : "";
}
