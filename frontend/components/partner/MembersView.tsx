"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import { Notice } from "@/components/ui/Notice";
import { useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

interface Member { id: string; user_id: string; email: string; display_name: string; role: string }

export function MembersView({ institutionId }: { institutionId: string }) {
  const { t } = useT();
  const L = useLabels();
  const [data, setData] = useState<{ members: Member[]; role: string } | null>(null);
  const [form, setForm] = useState({ email: "", display_name: "", role: "editor", password: "" });
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const load = useCallback(() => apiGet<{ members: Member[]; role: string }>(`${base(institutionId)}/members`).then(setData).catch((e) => setMsg({ kind: "error", text: e.message })), [institutionId]);
  useEffect(() => { load(); }, [load]);
  if (!data) return <p className="text-sm text-ink-muted">{t("partner.members.loading")}</p>;
  const isOwner = data.role === "owner";
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    try {
      await apiJson(`${base(institutionId)}/members`, "POST", { ...form, password: form.password || undefined });
      setForm({ email: "", display_name: "", role: "editor", password: "" });
      setMsg({ kind: "ok", text: t("partner.members.saved") });
      load();
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); }
  };
  const remove = async (m: Member) => {
    if (!window.confirm(t("partner.members.confirmRemove", { email: m.email }))) return;
    try { await apiJson(`${base(institutionId)}/members/${m.id}`, "DELETE"); load(); } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); }
  };
  return (
    <div className="space-y-6">
      <div><p className="eyebrow">{t("partner.members.eyebrow")}</p><h1 className="mt-1 text-[length:var(--text-h1)]">{t("partner.members.title")}</h1><p className="mt-1 text-sm text-ink-2">{t("partner.members.lede")}</p></div>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      <table className="table"><thead><tr><th>{t("partner.members.email")}</th><th>{t("partner.members.name")}</th><th>{t("partner.members.role")}</th><th /></tr></thead>
        <tbody>{data.members.map((m) => <tr key={m.id}><td>{m.email}</td><td>{m.display_name}</td><td><span className="badge">{L.role(m.role)}</span></td><td className="text-right">{isOwner && <button type="button" className="btn btn-danger text-xs" onClick={() => remove(m)}>{t("common.remove")}</button>}</td></tr>)}</tbody>
      </table>
      {isOwner && (
        <form onSubmit={add} className="card space-y-3">
          <h2 className="text-lg">{t("partner.members.addTitle")}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div><label htmlFor="m-email" className="field">{t("partner.members.email")}</label><input id="m-email" className="input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><label htmlFor="m-name" className="field">{t("partner.members.displayName")}</label><input id="m-name" className="input" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
            <div><label htmlFor="m-role" className="field">{t("partner.members.role")}</label><select id="m-role" className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{(["editor", "reviewer", "owner"] as const).map((r) => <option key={r} value={r}>{L.role(r)}</option>)}</select></div>
            <div><label htmlFor="m-pw" className="field">{t("partner.members.password")}</label><input id="m-pw" className="input" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          </div>
          <button type="submit" className="btn">{t("partner.members.save")}</button>
        </form>
      )}
    </div>
  );
}
