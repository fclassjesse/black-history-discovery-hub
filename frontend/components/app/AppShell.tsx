"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useMe } from "@/components/partner/usePartner";
import { PageSurface } from "@/components/layout/PageSurface";
import { AppSessionContext, readStoredInstitution, storeInstitution } from "@/lib/appSession";
import { CameraIcon, HomeIcon, PersonIcon, ReviewIcon, UploadIcon } from "@/components/app/AppIcons";
import { Link, useRoutePathname, useT } from "@/lib/i18n";

const TABS = [
  ["/app", "home", HomeIcon],
  ["/app/review", "review", ReviewIcon],
  ["/app/scan", "scan", CameraIcon],
  ["/app/upload", "upload", UploadIcon],
  ["/app/me", "me", PersonIcon],
] as const;

/**
 * The institution app: a phone-first shell (max 560px wide, bottom tab bar,
 * safe-area aware) over the same partner API the desktop portal uses.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRoutePathname();
  const isLogin = pathname === "/app/login";
  return (
    <div className="app-shell">
      <PageSurface tone="chalk" />
      {isLogin ? children : <Authed pathname={pathname}>{children}</Authed>}
    </div>
  );
}

function Authed({ pathname, children }: { pathname: string; children: ReactNode }) {
  const { t } = useT();
  const { me, loading } = useMe(false);
  const [stored, setStored] = useState<string | null>(() => readStoredInstitution());
  const setInstitution = useCallback((id: string) => { storeInstitution(id); setStored(id); }, []);

  const membership = useMemo(() => {
    if (!me) return null;
    return me.memberships.find((m) => m.institution_id === stored) ?? me.memberships[0] ?? null;
  }, [me, stored]);

  // remember the default choice so every screen agrees
  useEffect(() => { if (membership && membership.institution_id !== stored) storeInstitution(membership.institution_id); }, [membership, stored]);

  if (loading) return <main className="app-main grid place-items-center"><p className="text-sm text-ink-muted">{t("app.checking")}</p></main>;
  if (!me) {
    return (
      <main className="app-main grid content-center gap-4 px-5 text-center">
        <p className="display text-3xl">{t("app.staffOnly")}</p>
        <p className="text-ink-2">{t("app.signInWith")}</p>
        <Link href="/app/login" className="btn btn-lg mx-auto">{t("app.signIn")}</Link>
      </main>
    );
  }
  if (!membership) {
    return <main className="app-main grid place-items-center px-5 text-center"><p>{t("app.noInstitution")}</p></main>;
  }
  return (
    <AppSessionContext.Provider value={{ me, membership, setInstitution }}>
      <main className="app-main">{children}</main>
      <nav className="tabbar" aria-label={t("app.sections")}>
        {TABS.map(([href, key, Icon]) => {
          const active = href === "/app" ? pathname === "/app" : pathname.startsWith(href);
          const big = href === "/app/scan";
          return (
            <Link key={href} href={href} className={`tab ${big ? "tab-big" : ""}`} aria-current={active ? "page" : undefined}>
              <span className="tab-icon"><Icon /></span>
              <span className="tab-label">{t(`app.tabs.${key}`)}</span>
            </Link>
          );
        })}
      </nav>
    </AppSessionContext.Provider>
  );
}
