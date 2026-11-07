"use client";

import { useMe } from "@/components/partner/usePartner";
import { Link, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

export function InstitutionPicker() {
  const { t } = useT();
  const L = useLabels();
  const { me, loading } = useMe();
  if (loading) return <p className="mt-4 text-sm text-ink-muted">{t("partner.checking")}</p>;
  if (!me) return <p className="mt-4 text-sm">{t("partner.notSignedIn")} <Link href="/partner/login" className="underline">{t("partner.signInLink")}</Link>.</p>;
  return (
    <ul className="mt-8 grid gap-3 sm:grid-cols-2">
      {me.memberships.map((m) => (
        <li key={m.institution_id}>
          <Link href={`/partner/${m.institution_id}`} className="card block no-underline hover:no-underline">
            <span className="display block text-2xl">{m.institution_name}</span>
            <span className="mt-1 block text-sm text-ink-muted">{t("partner.roleOpen", { role: L.role(m.role) })}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
