"use client";

import { useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import { useAppSession } from "@/lib/appSession";
import type { InstitutionCard } from "@/lib/types";
import { PrecisionBadge } from "@/components/ui/Badges";
import { AppHeader } from "@/components/app/AppHeader";
import { Stamp } from "@/components/art/Stamps";
import { Link, useLocaleRouter, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

export function MeView() {
  const { t } = useT();
  const L = useLabels();
  const { me, membership, setInstitution } = useAppSession();
  const router = useLocaleRouter();
  const [profile, setProfile] = useState<(InstitutionCard & { role: string }) | null>(null);
  useEffect(() => { apiGet<InstitutionCard & { role: string }>(`${base(membership.institution_id)}/profile`).then(setProfile).catch(() => setProfile(null)); }, [membership.institution_id]);
  const logout = async () => { await apiJson("/api/partner/auth/logout", "POST"); router.push("/app/login"); };
  return (
    <div className="app-screen">
      <AppHeader eyebrow={t("app.me.eyebrow")} title={me.display_name} line={`${me.email} · ${L.role(membership.role)}`} />
      <section className="tile flex items-center gap-3">
        <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-chalk"><Stamp kind={profile?.kind ?? "archive"} className="h-12 w-12" /></span>
        <div className="min-w-0 flex-1">
          <p className="display text-lg leading-tight">{membership.institution_name}</p>
          <p className="mt-1 text-xs text-ink-muted">{profile ? [profile.city, profile.region].filter(Boolean).join(", ") : ""}</p>
          {profile && <div className="mt-1"><PrecisionBadge precision={profile.location_precision} /></div>}
        </div>
      </section>
      {me.memberships.length > 1 && (
        <section className="tile">
          <h2 className="kicker text-ink-muted">{t("app.me.switch")}</h2>
          <ul className="mt-1 grid gap-1">
            {me.memberships.map((m) => (
              <li key={m.institution_id}>
                <button type="button" className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm ${m.institution_id === membership.institution_id ? "bg-sun font-semibold" : "hover:bg-chalk"}`} onClick={() => setInstitution(m.institution_id)}>
                  <span>{m.institution_name}</span><span className="text-xs text-ink-muted">{L.role(m.role)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="tile text-sm">
        <h2 className="kicker text-ink-muted">{t("app.me.desktop")}</h2>
        <p className="mt-1 text-ink-2">{t("app.me.desktopText")}</p>
        <Link href={`/partner/${membership.institution_id}`} className="btn btn-secondary btn-sm mt-3">{t("app.me.openDesktop")}</Link>
      </section>
      <section className="tile text-sm">
        <h2 className="kicker text-ink-muted">{t("app.me.install")}</h2>
        <p className="mt-1 text-ink-2">{t("app.me.install1")}<strong>{t("app.me.addToHome")}</strong>{t("app.me.install2")}</p>
      </section>
      <button type="button" className="btn btn-lg" onClick={logout}>{t("app.me.signOut")}</button>
    </div>
  );
}
