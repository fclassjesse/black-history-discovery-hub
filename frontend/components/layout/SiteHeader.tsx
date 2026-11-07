"use client";

import { useEffect, useState } from "react";
import { Link, useRoutePathname, useT } from "@/lib/i18n";
import { LocaleSwitch } from "@/components/layout/LocaleSwitch";

const LINKS = [
  ["/", "ask"],
  ["/institutions", "institutions"],
  ["/advanced", "advanced"],
  ["/about/sources", "sources"],
  ["/app", "app"],
  ["/partner", "partner"],
] as const;

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const pathname = useRoutePathname();
  const { t } = useT();
  useEffect(() => {
    document.documentElement.style.overflow = open ? "hidden" : "";
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.documentElement.style.overflow = ""; };
  }, [open]);
  // the institution app has its own chrome
  if (pathname === "/app" || pathname.startsWith("/app/")) return null;
  const onFlame = pathname === "/";
  return (
    <>
      <header className={`site-header ${onFlame ? "on-flame" : ""}`}>
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between px-[var(--gutter)]">
          <span aria-hidden className="w-11" />
          <div className="flex items-center gap-2 sm:gap-3">
            <LocaleSwitch />
            <button type="button" className="btn btn-pill-chalk" aria-expanded={open} aria-controls="site-menu" onClick={() => setOpen((v) => !v)}>
              {open ? t("common.close") : t("common.menu")}
            </button>
          </div>
          <span aria-hidden className="w-11" />
        </div>
      </header>
      <div id="site-menu" className="menu-overlay" data-open={open} aria-hidden={!open} style={{ transition: "clip-path 700ms cubic-bezier(0.16,1,0.3,1)", visibility: open ? "visible" : "hidden", transitionProperty: open ? "clip-path" : "clip-path, visibility", transitionDelay: open ? "0s" : "0s, 700ms" }}>
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between px-[var(--gutter)]">
          <span aria-hidden className="w-11" />
          <button type="button" className="btn" onClick={() => setOpen(false)}>{t("common.close")}</button>
          <span aria-hidden className="w-11" />
        </div>
        <nav aria-label={t("header.siteMenu")} className="mx-auto grid w-full max-w-[1600px] content-center gap-2 px-[var(--gutter)] py-8 lg:grid-cols-[1fr_auto] lg:gap-12">
          <ul className="space-y-1 sm:space-y-3">
            {LINKS.map(([href, key], i) => (
              <li key={href} style={{ transition: `transform 600ms cubic-bezier(0.16,1,0.3,1) ${80 + i * 60}ms, opacity 500ms ${80 + i * 60}ms`, transform: open ? "none" : "translateY(30px)", opacity: open ? 1 : 0 }}>
                <Link href={href} className="menu-link" aria-current={pathname === href ? "page" : undefined} tabIndex={open ? 0 : -1} onClick={() => setOpen(false)}>
                  <span>{t(`header.links.${key}`)}</span><span className="arrow">→</span><small className="hidden sm:inline">{t(`header.links.${key}Hint`)}</small>
                </Link>
              </li>
            ))}
          </ul>
          <div className="plate-ink halftone max-w-sm self-end p-6" style={{ transition: "transform 700ms cubic-bezier(0.16,1,0.3,1) 300ms, opacity 500ms 300ms", transform: open ? "rotate(-2deg)" : "translateY(30px)", opacity: open ? 1 : 0 }}>
            <p className="kicker">{t("header.kicker")}</p>
            <p className="mt-2 text-sm leading-relaxed">{t("header.plate")}</p>
            <div className="mt-4"><LocaleSwitch className="lang-switch-ink" /></div>
          </div>
        </nav>
        <div className="mx-auto flex w-full max-w-[1600px] flex-wrap gap-x-6 gap-y-1 px-[var(--gutter)] pb-6 text-sm text-ink-muted">
          <span>{t("header.built")}</span>
          <a href="/api-docs" className="underline" tabIndex={open ? 0 : -1} onClick={() => setOpen(false)}>{t("header.partnerApi")}</a>
        </div>
      </div>
    </>
  );
}
