"use client";

import { apiJson } from "@/lib/api";
import { useMe } from "@/components/partner/usePartner";
import { Notice } from "@/components/ui/Notice";
import { Link, useLocaleRouter, useRoutePathname, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

const NAV = [["", "dashboard"], ["/records", "records"], ["/review", "review"], ["/import", "import"], ["/finding-aids", "findingAids"], ["/shelf-scan", "shelfScan"], ["/profile", "profile"], ["/members", "members"]] as const;

export function PartnerShell({ institutionId, children }: { institutionId: string; children: React.ReactNode }) {
  const { t } = useT();
  const L = useLabels();
  const { me, loading } = useMe();
  const pathname = useRoutePathname();
  const router = useLocaleRouter();
  if (loading) return <p className="p-6 text-sm text-ink-muted">{t("partner.checking")}</p>;
  if (!me) return null;
  const membership = me.memberships.find((m) => m.institution_id === institutionId);
  if (!membership) {
    return <div className="mx-auto max-w-2xl p-6"><Notice kind="error">{t("partner.notMember")} <Link href="/partner" className="underline">{t("partner.chooseOne")}</Link>.</Notice></div>;
  }
  const root = `/partner/${institutionId}`;
  const logout = async () => { await apiJson("/api/partner/auth/logout", "POST"); router.push("/partner/login"); };
  return (
    <div className="mx-auto grid max-w-[1600px] gap-6 px-[var(--gutter)] py-6 lg:grid-cols-[260px_1fr]">
      <aside className="plate-ink halftone self-start p-5 lg:sticky lg:top-[calc(var(--header-h)+8px)]">
        <p className="kicker text-cream/70">{t("partner.eyebrow")}</p>
        <p className="display mt-1 text-xl leading-tight">{membership.institution_name}</p>
        <p className="mt-1 text-xs text-cream/70">{me.email} · {L.role(membership.role)}</p>
        <nav aria-label={t("partner.navAria")} className="mt-5">
          <ul className="space-y-0.5 text-sm">
            {NAV.map(([p, key]) => {
              const href = root + p;
              const active = p === "" ? pathname === root : pathname.startsWith(href);
              return <li key={p}><Link href={href} aria-current={active ? "page" : undefined} className={`block rounded-xl px-3 py-2 no-underline transition-colors ${active ? "bg-sun font-semibold text-ink" : "text-cream hover:bg-cream/15"}`}>{t(`partner.nav.${key}`)}</Link></li>;
            })}
          </ul>
        </nav>
        <div className="mt-5 flex flex-col items-start gap-2 text-xs text-cream/80">
          {me.memberships.length > 1 && <Link href="/partner" className="underline">{t("partner.switch")}</Link>}
          <Link href="/app" className="underline">{t("partner.mobileApp")}</Link>
          <a href="/api-docs" className="underline">{t("common.apiDocs")}</a>
          <button type="button" onClick={logout} className="btn btn-pill-chalk btn-sm mt-1">{t("partner.signOut")}</button>
        </div>
      </aside>
      <div className="min-w-0 pb-[var(--space-section)]">{children}</div>
    </div>
  );
}
