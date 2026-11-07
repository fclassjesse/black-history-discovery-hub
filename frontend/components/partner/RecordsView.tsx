"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import type { RecordCard, ReviewStatus } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { AccessBadge, StatusBadge, VerificationBadge } from "@/components/ui/Badges";
import { useLabels } from "@/lib/labels";
import { Link, useT } from "@/lib/i18n";

interface ListResp { total: number; results: RecordCard[]; role: string; actions: Record<string, boolean> }
const ACTIONS: [string, string][] = [["submit", "btn-secondary"], ["return", "btn-secondary"], ["publish", ""], ["withdraw", "btn-danger"], ["reopen", "btn-secondary"]];
const FROM: Record<string, ReviewStatus[]> = { submit: ["draft"], return: ["in_review"], publish: ["draft", "in_review"], withdraw: ["published", "in_review"], reopen: ["withdrawn"] };

export function RecordsView({ institutionId, review = false }: { institutionId: string; review?: boolean }) {
  const { t, locale } = useT();
  const L = useLabels();
  const sp = useSearchParams();
  const [status, setStatus] = useState<string>(review ? "in_review" : sp.get("status") ?? "");
  const [data, setData] = useState<ListResp | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<RecordCard | null>(null);
  const [creating, setCreating] = useState(false);
  const load = useCallback(() => apiGet<ListResp>(`${base(institutionId)}/records?page_size=100${status ? `&status=${status}` : ""}`).then(setData).catch((e) => setMsg({ kind: "error", text: e.message })), [institutionId, status]);
  useEffect(() => { load(); }, [load, locale]);

  const act = async (r: RecordCard, action: string) => {
    setMsg(null);
    try {
      await apiJson(`${base(institutionId)}/records/${r.id}/${action}`, "POST", { note: null });
      setMsg({ kind: "ok", text: `${t("partner.records.done", { action: t(`partner.records.actions.${action}`), title: r.title })} ${action === "publish" ? t("partner.records.nowPublic") : action === "withdraw" ? t("partner.records.leftPublic") : ""}` });
      load();
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); }
  };
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="eyebrow">{review ? t("partner.records.reviewEyebrow") : t("partner.records.eyebrow")}</p><h1 className="mt-1 text-[length:var(--text-h1)]">{review ? t("partner.records.reviewTitle") : t("partner.records.title")}</h1></div>
        <div className="flex items-end gap-3">
          <div><label htmlFor="status" className="field">{t("partner.records.status")}</label><select id="status" className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">{t("common.all")}</option>{(["draft", "in_review", "published", "withdrawn"] as const).map((s) => <option key={s} value={s}>{L.status(s)}</option>)}</select></div>
          <button type="button" className="btn" onClick={() => setCreating(true)}>{t("partner.records.manualEntry")}</button>
        </div>
      </div>
      <p className="text-sm text-ink-2">{t("partner.records.workflow1")}<em>{t("partner.records.workflowPublished")}</em>{t("partner.records.workflow2")}</p>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {creating && <RecordForm institutionId={institutionId} onDone={() => { setCreating(false); load(); }} onCancel={() => setCreating(false)} />}
      {editing && <RecordForm institutionId={institutionId} record={editing} onDone={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />}
      {!data ? <p className="text-sm text-ink-muted">{t("common.loading")}</p> : data.results.length === 0 ? <Notice>{status ? t("partner.records.noRecordsStatus", { status: L.status(status) }) : t("partner.records.noRecordsYet")}</Notice> : (
        <ul className="space-y-3">
          {data.results.map((r) => (
            <li key={r.id} className="card">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="text-lg leading-snug">{r.title}</h2>
                  <p className="text-sm text-ink-2">{r.creators.join("; ")}{r.date_text ? ` · ${r.date_text}` : ""} · {L.resourceType(r.resource_type)}{r.call_number ? ` · ${t("common.callNo", { n: r.call_number })}` : ""}</p>
                  <p className="mt-1 text-xs text-ink-muted">{t("partner.records.sourceLine", { source: r.source_system, adapter: String(r.provenance.adapter ?? "") })}{r.provenance.created_by ? ` ${t("partner.records.by", { who: String(r.provenance.created_by) })}` : ""}</p>
                </div>
                <div className="flex flex-wrap gap-1"><StatusBadge status={r.review_status} /><AccessBadge access={r.access_type} /><VerificationBadge verification={r.holding_verification} /></div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                <button type="button" className="btn btn-secondary" onClick={() => setEditing(r)}>{t("common.edit")}</button>
                {ACTIONS.filter(([a]) => data.actions[a] && FROM[a].includes(r.review_status)).map(([a, cls]) => <button key={a} type="button" className={`btn ${cls}`} onClick={() => act(r, a)}>{t(`partner.records.actions.${a}`)}</button>)}
                {r.review_status === "published" && <Link href={`/records/${r.id}`} className="btn btn-quiet" target="_blank">{t("partner.records.viewPublic")}</Link>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RecordForm({ institutionId, record, onDone, onCancel }: { institutionId: string; record?: RecordCard; onDone: () => void; onCancel: () => void }) {
  const { t } = useT();
  const L = useLabels();
  const F = (k: string) => t(`partner.records.fields.${k}`);
  const [f, setF] = useState({
    title: record?.title ?? "", creators: record?.creators.join("; ") ?? "", description: record?.description ?? "", subjects: record?.subjects.join("; ") ?? "", date_text: record?.date_text ?? "",
    resource_type: record?.resource_type ?? "book", language: record?.language.join("; ") ?? "", original_url: record?.original_url ?? "", digital_url: record?.digital_url ?? "", rights: record?.rights ?? "",
    access_type: record?.access_type ?? "physical", access_note: record?.access_note ?? "", call_number: record?.call_number ?? "", shelf_label: record?.shelf_label ?? "",
    holding_verification: record?.holding_verification === "verified_partner" ? "verified_partner" : "unverified",
  });
  const [confirmHolding, setConfirmHolding] = useState(record?.holding_verification === "verified_partner");
  const [err, setErr] = useState<string | null>(null);
  const split = (s: string) => s.split(/[;|]/).map((x) => x.trim()).filter(Boolean);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const body = { ...f, confirm_holding: confirmHolding, creators: split(f.creators), subjects: split(f.subjects), language: split(f.language), original_url: f.original_url || null, digital_url: f.digital_url || null, description: f.description || null, rights: f.rights || null, access_note: f.access_note || null, call_number: f.call_number || null, shelf_label: f.shelf_label || null, date_text: f.date_text || null };
    try {
      if (record) await apiJson(`${base(institutionId)}/records/${record.id}`, "PATCH", body);
      else await apiJson(`${base(institutionId)}/records`, "POST", body);
      onDone();
    } catch (e2) { setErr((e2 as Error).message); }
  };
  const field = (k: keyof typeof f, label: string, extra?: React.ReactNode) => (
    <div><label htmlFor={`r-${k}`} className="field">{label}</label>{extra ?? <input id={`r-${k}`} className="input" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />}</div>
  );
  return (
    <form onSubmit={submit} className="card space-y-3 border-teal">
      <h2 className="text-lg">{record ? t("partner.records.editRecord") : t("partner.records.manualTitle")}</h2>
      {err && <Notice kind="error">{err}</Notice>}
      <div className="grid gap-3 sm:grid-cols-2">
        {field("title", F("title"))}
        {field("creators", F("creators"))}
        {field("date_text", F("date"))}
        {field("resource_type", F("resourceType"), <select id="r-resource_type" className="input" value={f.resource_type} onChange={(e) => setF({ ...f, resource_type: e.target.value })}>{L.resourceTypes.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>)}
        {field("subjects", F("subjects"))}
        {field("language", F("languages"))}
        {field("original_url", F("originalUrl"))}
        {field("digital_url", F("digitalUrl"))}
        {field("access_type", F("access"), <select id="r-access_type" className="input" value={f.access_type} onChange={(e) => setF({ ...f, access_type: e.target.value as typeof f.access_type })}>{(["physical", "online", "both", "unknown"] as const).map((a) => <option key={a} value={a}>{L.access(a)}</option>)}</select>)}
        {field("holding_verification", F("holding"), <select id="r-holding_verification" className="input" value={f.holding_verification} onChange={(e) => setF({ ...f, holding_verification: e.target.value })}><option value="unverified">{F("unverified")}</option><option value="verified_partner">{F("verified")}</option></select>)}
        {field("call_number", F("callNumber"))}
        {field("shelf_label", F("shelf"))}
        {field("rights", F("rights"))}
        {field("access_note", F("accessNote"))}
      </div>
      <div><label htmlFor="r-description" className="field">{F("description")}</label><textarea id="r-description" className="input" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></div>
      {f.holding_verification === "verified_partner" && (
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="checkbox mt-0.5" checked={confirmHolding} onChange={(e) => setConfirmHolding(e.target.checked)} /><span><strong>{t("partner.records.confirmHolding")}</strong> {t("partner.records.confirmNote")}</span></label>
      )}
      <div className="flex gap-2"><button type="submit" className="btn">{record ? t("partner.records.saveChanges") : t("partner.records.createDraft")}</button><button type="button" className="btn btn-secondary" onClick={onCancel}>{t("common.cancel")}</button></div>
    </form>
  );
}
