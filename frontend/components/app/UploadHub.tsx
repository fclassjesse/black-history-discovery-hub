"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiForm, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import { useAppSession } from "@/lib/appSession";
import { character } from "@/lib/character";
import type { ImportBatch, RecordCard } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { AppHeader } from "@/components/app/AppHeader";
import { useLabels } from "@/lib/labels";
import { FileIcon, UploadIcon } from "@/components/app/AppIcons";
import { useFormat, useT } from "@/lib/i18n";

type Tab = "file" | "pdf" | "manual";

/** Three ways in: a CSV/JSON file (preview → commit), a PDF finding aid, or one record by hand. All create drafts. */
export function UploadHub() {
  const { t } = useT();
  const sp = useSearchParams();
  const [tab, setTab] = useState<Tab>((sp.get("tab") as Tab) || "file");
  return (
    <div className="app-screen">
      <AppHeader eyebrow={t("app.upload.eyebrow")} title={t("app.upload.title")} line={t("app.upload.line")} />
      <div className="seg" role="tablist" aria-label={t("app.upload.typeAria")}>
        {(["file", "pdf", "manual"] as const).map((k) => <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{t(`app.upload.tabs.${k}`)}</button>)}
      </div>
      {tab === "file" && <FileImport />}
      {tab === "pdf" && <PdfImport />}
      {tab === "manual" && <ManualEntry />}
    </div>
  );
}

function FileImport() {
  const { t } = useT();
  const fmt = useFormat();
  const { membership } = useAppSession();
  const root = base(membership.institution_id);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setMsg(null);
    const fd = new FormData(); fd.append("file", file);
    try { setBatch(await apiForm<ImportBatch>(`${root}/imports`, fd)); character.set("celebrate"); } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  const remap = async (field: string, header: string) => {
    if (!batch) return;
    try { setBatch(await apiJson<ImportBatch>(`${root}/imports/${batch.id}/mapping`, "PUT", { fields: { ...batch.mapping.fields, [field]: header || null } })); } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); }
  };
  const commit = async () => {
    if (!batch) return;
    setBusy(true); setMsg(null);
    try {
      const r = await apiJson<{ created_drafts: number }>(`${root}/imports/${batch.id}/commit`, "POST", { skip_duplicates: true });
      setBatch({ ...batch, status: "committed", committed_count: r.created_drafts });
      setMsg({ kind: "ok", text: t("app.upload.committed", { n: r.created_drafts }) });
      character.set("celebrate");
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  const valid = batch ? batch.row_count - batch.error_count - batch.duplicate_count : 0;
  return (
    <div className="grid gap-3">
      <label className="big-action cursor-pointer"><UploadIcon /> {busy ? t("app.upload.uploading") : t("app.upload.chooseFile")}<input type="file" accept=".csv,.json,text/csv,application/json" className="sr-only" disabled={busy} onChange={(e) => pick(e.target.files?.[0])} /></label>
      <p className="text-xs text-ink-muted">{t("app.upload.needColumns")} <a href="/partner-import-template.csv" className="underline" download>{t("app.upload.downloadTemplate")}</a>.</p>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {batch && (
        <section className="tile grid gap-3">
          <div><p className="kicker text-ink-muted">{t("app.upload.preview")}</p><p className="display text-lg leading-tight">{batch.filename}</p></div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-2xl bg-chalk p-2"><span className="display tnum block text-2xl">{fmt.number(batch.row_count)}</span><span className="text-xs text-ink-muted">{t("app.upload.rows")}</span></div>
            <div className={`rounded-2xl p-2 ${batch.error_count ? "bg-danger-tint" : "bg-chalk"}`}><span className="display tnum block text-2xl">{fmt.number(batch.error_count)}</span><span className="text-xs text-ink-muted">{t("app.upload.errors")}</span></div>
            <div className={`rounded-2xl p-2 ${batch.duplicate_count ? "bg-sun-tint" : "bg-chalk"}`}><span className="display tnum block text-2xl">{fmt.number(batch.duplicate_count)}</span><span className="text-xs text-ink-muted">{t("app.upload.duplicates")}</span></div>
          </div>
          <button type="button" className="text-left text-sm underline" onClick={() => setMapOpen((v) => !v)}>{mapOpen ? t("app.upload.hideMapping") : t("app.upload.checkMapping")}</button>
          {mapOpen && (
            <div className="grid gap-2">
              {batch.canonical_fields.map((f) => (
                <label key={f} className="grid grid-cols-[1fr_1.3fr] items-center gap-2 text-xs"><span className="text-ink-muted">{f}{f === "title" ? " *" : ""}</span>
                  <select className="input py-1 text-sm" value={batch.mapping.fields[f] ?? ""} disabled={batch.status !== "preview"} onChange={(e) => remap(f, e.target.value)}>
                    <option value="">{t("app.upload.notMapped")}</option>
                    {batch.mapping.headers.map((h) => <option key={h} value={h}>{h}</option>)}
                  </select>
                </label>
              ))}
            </div>
          )}
          {(batch.preview ?? []).slice(0, 5).map((r) => (
            <div key={r.row_number} className="rule pt-2 text-sm"><span className="tnum text-ink-muted">#{r.row_number}</span> {String(r.values.title ?? t("app.upload.noTitle"))} {r.errors.map((e) => <span key={e} className="badge badge-danger ml-1">{e}</span>)}{r.duplicate_of && <span className="badge badge-physical ml-1">{t("app.upload.duplicate")}</span>}</div>
          ))}
          {batch.status === "preview" ? <button type="button" className="btn" onClick={commit} disabled={busy || valid <= 0}>{t("app.upload.createDrafts", { n: valid })}</button> : <p className="text-sm text-moss-deep">{t("app.upload.committedLine", { n: batch.committed_count })}</p>}
        </section>
      )}
    </div>
  );
}

function PdfImport() {
  const { t, tn } = useT();
  const { membership } = useAppSession();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [created, setCreated] = useState<(RecordCard & { pages: number }) | null>(null);
  const [fileName, setFileName] = useState("");
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    const fd = new FormData(e.currentTarget);
    try {
      const r = await apiForm<RecordCard & { pages: number }>(`${base(membership.institution_id)}/finding-aids`, fd);
      setCreated(r); setMsg({ kind: "ok", text: t("app.upload.pdfCreated", { n: r.pages }) }); character.set("celebrate");
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="grid gap-3">
      <label className="big-action secondary cursor-pointer"><FileIcon /> {fileName || t("app.upload.choosePdf")}<input name="file" type="file" accept="application/pdf,.pdf" className="sr-only" required onChange={(e) => setFileName(e.target.files?.[0]?.name ?? "")} /></label>
      <div><label htmlFor="fa-title" className="field">{t("app.upload.titleOptional")}</label><input id="fa-title" name="title" className="input" /></div>
      <div><label htmlFor="fa-url" className="field">{t("app.upload.catalogueLink")}</label><input id="fa-url" name="original_url" className="input" inputMode="url" placeholder="https://…" /></div>
      <button type="submit" className="btn btn-lg" disabled={busy}>{busy ? t("app.upload.readingPages") : t("app.upload.createDraft")}</button>
      <p className="text-xs text-ink-muted">{t("app.upload.pdfNote")}</p>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {created && <div className="tile text-sm"><p className="display text-lg">{created.title}</p><p className="text-ink-muted">{t("app.upload.draft")} · {tn("common.pages", created.pages)}</p></div>}
    </form>
  );
}

function ManualEntry() {
  const { t } = useT();
  const L = useLabels();
  const { membership } = useAppSession();
  const [f, setF] = useState({ title: "", creators: "", date_text: "", resource_type: "book", access_type: "physical", call_number: "", description: "" });
  const [holds, setHolds] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await apiJson(`${base(membership.institution_id)}/records`, "POST", {
        title: f.title, creators: f.creators.split(/[;|]/).map((x) => x.trim()).filter(Boolean), subjects: [], language: [], date_text: f.date_text || null, resource_type: f.resource_type,
        access_type: f.access_type, call_number: f.call_number || null, description: f.description || null, holding_verification: holds ? "verified_partner" : "unverified", confirm_holding: holds,
      });
      setMsg({ kind: "ok", text: t("app.upload.manual.created", { title: f.title }) });
      setF({ title: "", creators: "", date_text: "", resource_type: "book", access_type: "physical", call_number: "", description: "" });
      character.set("celebrate");
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  const M = (k: string) => t(`app.upload.manual.${k}`);
  return (
    <form onSubmit={submit} className="tile grid gap-3">
      <div><label htmlFor="m-title" className="field">{M("title")}</label><input id="m-title" className="input" value={f.title} onChange={set("title")} required /></div>
      <div><label htmlFor="m-creators" className="field">{M("creators")}</label><input id="m-creators" className="input" value={f.creators} onChange={set("creators")} /></div>
      <div className="grid grid-cols-2 gap-2">
        <div><label htmlFor="m-date" className="field">{M("date")}</label><input id="m-date" className="input" value={f.date_text} onChange={set("date_text")} placeholder="1983" /></div>
        <div><label htmlFor="m-call" className="field">{M("callNumber")}</label><input id="m-call" className="input tnum" value={f.call_number} onChange={set("call_number")} /></div>
        <div><label htmlFor="m-type" className="field">{M("type")}</label><select id="m-type" className="input" value={f.resource_type} onChange={set("resource_type")}>{L.resourceTypes.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <div><label htmlFor="m-access" className="field">{M("access")}</label><select id="m-access" className="input" value={f.access_type} onChange={set("access_type")}>{(["physical", "online", "both"] as const).map((a) => <option key={a} value={a}>{L.access(a)}</option>)}</select></div>
      </div>
      <div><label htmlFor="m-desc" className="field">{M("description")}</label><textarea id="m-desc" className="input" rows={3} value={f.description} onChange={set("description")} /></div>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="checkbox mt-0.5" checked={holds} onChange={(e) => setHolds(e.target.checked)} /><span><strong>{M("holds")}</strong> {M("holdsNote")}</span></label>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      <button type="submit" className="btn btn-lg" disabled={busy || !f.title.trim()}>{busy ? M("saving") : t("app.upload.createDraft")}</button>
    </form>
  );
}
