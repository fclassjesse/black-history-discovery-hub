"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { InstitutionCard } from "@/lib/types";
import { useLabels } from "@/lib/labels";
import { useLocaleRouter, useT } from "@/lib/i18n";

export function AdvancedForm() {
  const { t } = useT();
  const L = useLabels();
  const sp = useSearchParams();
  const router = useLocaleRouter();
  const [institutions, setInstitutions] = useState<InstitutionCard[]>([]);
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [types, setTypes] = useState<string[]>((sp.get("types") ?? "").split(",").filter(Boolean));
  const [access, setAccess] = useState(sp.get("access") ?? "");
  const [institution, setInstitution] = useState(sp.get("institution") ?? "");
  const [lang, setLang] = useState(sp.get("lang") ?? "");
  const [dateFrom, setDateFrom] = useState(sp.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(sp.get("date_to") ?? "");
  const [identifier, setIdentifier] = useState(sp.get("identifier") ?? "");
  const [location, setLocation] = useState(sp.get("location") ?? "");
  const [verification, setVerification] = useState(sp.get("verification") ?? "");
  useEffect(() => { apiGet<{ institutions: InstitutionCard[] }>("/api/institutions").then((d) => setInstitutions(d.institutions)).catch(() => {}); }, []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const p = new URLSearchParams();
    p.set("mode", "advanced");
    if (q.trim()) p.set("q", q.trim());
    if (types.length) p.set("types", types.join(","));
    if (access) p.set("access", access);
    if (institution) p.set("institution", institution);
    if (lang) p.set("lang", lang);
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    if (identifier) p.set("identifier", identifier);
    if (location) p.set("location", location);
    if (verification) p.set("verification", verification);
    router.push(`/?${p.toString()}`);
  };
  return (
    <form onSubmit={submit} className="plate-white mt-10 space-y-6 p-6 sm:p-8">
      <div>
        <label htmlFor="adv-q" className="field">{t("advanced.query")}</label>
        <input id="adv-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={'"Black Loyalists" -Sierra'} />
        <p className="mt-1 text-xs text-ink-muted">{t("advanced.examples")} <code className="rounded bg-chalk px-1">&quot;Book of Negroes&quot;</code> · <code className="rounded bg-chalk px-1">Africville or Preston</code> · <code className="rounded bg-chalk px-1">Loyalists -Sierra</code></p>
      </div>
      <fieldset>
        <legend className="field">{t("advanced.resourceType")}</legend>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
          {L.resourceTypes.map(([v, label]) => (
            <label key={v} className="flex items-center gap-2 text-sm"><input type="checkbox" className="checkbox" checked={types.includes(v)} onChange={() => setTypes(types.includes(v) ? types.filter((x) => x !== v) : [...types, v])} />{label}</label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <div><label htmlFor="adv-from" className="field">{t("advanced.dateFrom")}</label><input id="adv-from" className="input tnum" inputMode="numeric" value={dateFrom} onChange={(e) => setDateFrom(e.target.value.replace(/\D/g, "").slice(0, 4))} /></div>
        <div><label htmlFor="adv-to" className="field">{t("advanced.dateTo")}</label><input id="adv-to" className="input tnum" inputMode="numeric" value={dateTo} onChange={(e) => setDateTo(e.target.value.replace(/\D/g, "").slice(0, 4))} /></div>
        <div><label htmlFor="adv-lang" className="field">{t("advanced.language")}</label><input id="adv-lang" className="input" value={lang} onChange={(e) => setLang(e.target.value.trim().toLowerCase())} /></div>
        <div><label htmlFor="adv-loc" className="field">{t("advanced.location")}</label><input id="adv-loc" className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder={t("advanced.locationPlaceholder")} /></div>
        <div>
          <label htmlFor="adv-inst" className="field">{t("advanced.institution")}</label>
          <select id="adv-inst" className="input" value={institution} onChange={(e) => setInstitution(e.target.value)}>
            <option value="">{t("common.any")}</option>
            {institutions.map((i) => <option key={i.id} value={i.slug}>{i.name}</option>)}
          </select>
        </div>
        <div><label htmlFor="adv-id" className="field">{t("advanced.identifier")}</label><input id="adv-id" className="input tnum" value={identifier} onChange={(e) => setIdentifier(e.target.value)} /></div>
        <div>
          <label htmlFor="adv-access" className="field">{t("advanced.access")}</label>
          <select id="adv-access" className="input" value={access} onChange={(e) => setAccess(e.target.value)}>
            <option value="">{t("advanced.onlineOrPhysical")}</option><option value="online">{t("access.online")}</option><option value="physical">{t("access.physical")}</option>
          </select>
        </div>
        <div>
          <label htmlFor="adv-ver" className="field">{t("advanced.verification")}</label>
          <select id="adv-ver" className="input" value={verification} onChange={(e) => setVerification(e.target.value)}>
            <option value="">{t("common.any")}</option><option value="verified_partner">{t("advanced.verPartner")}</option><option value="catalogue_record">{t("advanced.verCatalogue")}</option><option value="unverified">{t("advanced.verUnverified")}</option><option value="demo">{t("advanced.verDemo")}</option>
          </select>
        </div>
      </div>
      <div className="flex gap-3 pt-2"><button type="submit" className="btn btn-lg">{t("advanced.run")}</button><button type="reset" className="btn btn-secondary btn-lg" onClick={() => router.push("/advanced")}>{t("advanced.reset")}</button></div>
    </form>
  );
}
