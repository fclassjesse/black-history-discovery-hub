import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_COOKIE, LOCALE_HEADER, type Locale } from "@/lib/i18n-core";

const COOKIE = { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax" as const };

/**
 * Locale routing. `/fr/x` is served by the `/x` route with `x-locale: fr`; `/en/x` redirects to `/x` (and remembers
 * English); a bare `/x` with a remembered French preference redirects to `/fr/x`. API and asset paths are excluded
 * by the matcher below.
 */
export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const m = pathname.match(/^\/(en|fr)(\/.*)?$/);
  if (m) {
    const locale = m[1] as Locale;
    const rest = m[2] && m[2] !== "/" ? m[2] : "/";
    if (locale === "en") {
      const res = NextResponse.redirect(new URL(rest + search, req.url));
      res.cookies.set(LOCALE_COOKIE, "en", COOKIE);
      return res;
    }
    const url = req.nextUrl.clone();
    url.pathname = rest;
    const headers = new Headers(req.headers);
    headers.set(LOCALE_HEADER, locale);
    const res = NextResponse.rewrite(url, { request: { headers } });
    res.cookies.set(LOCALE_COOKIE, locale, COOKIE);
    return res;
  }
  const pref = req.cookies.get(LOCALE_COOKIE)?.value;
  if (pref === "fr") {
    return NextResponse.redirect(new URL(`/fr${pathname === "/" ? "" : pathname}${search}`, req.url));
  }
  const headers = new Headers(req.headers);
  headers.set(LOCALE_HEADER, "en");
  return NextResponse.next({ request: { headers } });
}

export const config = {
  // pages only: skip the API proxy, Next internals, the OpenAPI/docs rewrites and any file with an extension
  matcher: ["/((?!api|api-docs|openapi\\.json|_next|.*\\..*).*)"],
};
