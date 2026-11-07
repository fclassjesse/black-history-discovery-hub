"use client";

import { useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import type { InstitutionCard } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { PrecisionBadge } from "@/components/ui/Badges";
import { useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

type Profile = InstitutionCard & { role: string };
const FIELDS: [keyof InstitutionCard, string?][] = [
  ["name"], ["kind"], ["description", "textarea"], ["website_url"], ["catalogue_url"],
  ["address"], ["city"], ["region"], ["country"], ["contact_email"], ["contact_phone"],
  ["access_requirements", "textarea"], ["collection_summary", "textarea"],
];

export function ProfileForm({ institutionId }: { institutionId: string }) {
  const { t } = useT();
  const L = useLabels();
  const [p, setP] = useState<Profile | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [verify, setVerify] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  useEffect(() => {
    apiGet<Profile>(`${base(institutionId)}/profile`).then((d) => {
      setP(d);
      setForm(Object.fromEntries(FIELDS.map(([k]) => [k, (d[k] as string | null) ?? ""])));
      setLat(d.latitude != null ? String(d.latitude) : "");
      setLon(d.longitude != null ? String(d.longitude) : "");
    }).catch((e) => setMsg({ kind: "error", text: e.message }));
  }, [institutionId]);
  if (!p) return <p className="text-sm text-ink-muted">{t("partner.profile.loading")}</p>;
  const canEdit = p.role === "owner" || p.role === "editor";
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    try {
      const body: Record<string, unknown> = { ...form };
      if (lat !== "" || lon !== "") { body.latitude = lat === "" ? null : Number(lat); body.longitude = lon === "" ? null : Number(lon); }
      else { body.latitude = null; body.longitude = null; }
      if (verify) body.verify_location = true;
      const d = await apiJson<Profile>(`${base(institutionId)}/profile`, "PUT", body);
      setP(d);
      setVerify(false);
      setMsg({ kind: "ok", text: t("partner.profile.saved") });
    } catch (err) {
      setMsg({ kind: "error", text: (err as Error).message });
    }
  };
  return (
    <form onSubmit={submit} className="space-y-5">
      <div><p className="eyebrow">{t("partner.profile.eyebrow")}</p><h1 className="mt-1 text-[length:var(--text-h1)]">{p.name}</h1></div>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {!canEdit && <Notice>{t("partner.profile.readOnly", { role: L.role(p.role) })}</Notice>}
      <div className="grid gap-4 sm:grid-cols-2">
        {FIELDS.map(([k, kind]) => (
          <div key={k} className={kind === "textarea" ? "sm:col-span-2" : ""}>
            <label htmlFor={`f-${k}`} className="field">{t(`partner.profile.fields.${k}`)}</label>
            {kind === "textarea" ? <textarea id={`f-${k}`} className="input" rows={3} value={form[k] ?? ""} disabled={!canEdit} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              : <input id={`f-${k}`} className="input" value={form[k] ?? ""} disabled={!canEdit} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />}
          </div>
        ))}
      </div>
      <fieldset className="card">
        <legend className="eyebrow px-1">{t("partner.profile.mapLocation")}</legend>
        <p className="text-sm text-ink-2">{t("partner.profile.current")} <PrecisionBadge precision={p.location_precision} /> {p.location_source && <span className="text-xs text-ink-muted">— {p.location_source}</span>}</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div><label htmlFor="lat" className="field">{t("partner.profile.latitude")}</label><input id="lat" className="input tnum" value={lat} disabled={!canEdit} onChange={(e) => setLat(e.target.value)} placeholder="44.7069" /></div>
          <div><label htmlFor="lon" className="field">{t("partner.profile.longitude")}</label><input id="lon" className="input tnum" value={lon} disabled={!canEdit} onChange={(e) => setLon(e.target.value)} placeholder="-63.4746" /></div>
        </div>
        <label className="mt-3 flex items-start gap-2 text-sm">
          <input type="checkbox" className="checkbox mt-0.5" checked={verify} disabled={p.role !== "owner" || !canEdit} onChange={(e) => setVerify(e.target.checked)} />
          <span>{t("partner.profile.verify1")}<em>{t("partner.profile.verifyEm")}</em>{t("partner.profile.verify2")}</span>
        </label>
      </fieldset>
      <button type="submit" className="btn" disabled={!canEdit}>{t("partner.profile.save")}</button>
    </form>
  );
}
