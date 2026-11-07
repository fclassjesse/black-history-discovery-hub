"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";
import { LOCALES, LOCALE_NAME, switchLocalePath, useLocale, useSearchString, useT } from "@/lib/i18n";

function Switch({ className = "" }: { className?: string }) {
  const locale = useLocale();
  const pathname = usePathname();
  const search = useSearchString();
  const { t } = useT();
  return (
    <nav aria-label={t("header.languageAria")} className={`lang-switch ${className}`}>
      {LOCALES.map((l, i) => (
        <span key={l} className="contents">
          {i > 0 && <span aria-hidden className="lang-sep">|</span>}
          {l === locale ? (
            <span className="lang-current" aria-current="true" lang={l}>{l.toUpperCase()}</span>
          ) : (
            // plain <a>: the proxy handles the prefix (and `/en/…` redirects while remembering the choice)
            <a href={switchLocalePath(pathname, search, l)} className="lang-link" lang={l} hrefLang={l} aria-label={t("common.switchTo", { lang: LOCALE_NAME[l] })} title={LOCALE_NAME[l]}>{l.toUpperCase()}</a>
          )}
        </span>
      ))}
    </nav>
  );
}

/** EN | FR. Visible in the header and the institution app. */
export function LocaleSwitch(props: { className?: string }) {
  return <Suspense fallback={null}><Switch {...props} /></Suspense>;
}
