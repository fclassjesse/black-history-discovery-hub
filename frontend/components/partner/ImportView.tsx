"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiForm, apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import type { ImportBatch } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { useT } from "@/lib/i18n";

export function ImportView({ institutionId }: { institutionId: string }) {
  const { t, tn } = useT();
  const sp = useSearchParams();
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [result, setResult] = useState<{ created_drafts: number; skipped: { row_number: number; reason: string }[] } | null>(null);
  useEffect(() => {
    apiGet<{ batches: ImportBatch[] }>(`${base(institutionId)}/imports`).then((d) => setBatches(d.batches)).catch(() => {});
    const id = sp.get("batch");
    if (id) apiGet<ImportBatch>(`${base(institutionId)}/imports/${id}`).then(setBatch).catch((e) => setMsg({ kind: "error", text: e.message }));
  }, [institutionId, sp]);

  const upload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const file = (e.currentTarget.elements.namedItem("file") as HTMLInputElement).files?.[0];
    if (!file) return;
    setBusy(true); setMsg(null); setResult(null);
    const fd = new FormData(); fd.append("file", file);
    try { setBatch(await apiForm<ImportBatch>(`${base(institutionId)}/imports`, fd)); } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  const remap = async (field: string, header: string) => {
    if (!batch) return;
    try { setBatch(await apiJson<ImportBatch>(`${base(institutionId)}/imports/${batch.id}/mapping`, "PUT", { fields: { ...batch.mapping.fields, [field]: header || null } })); } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); }
  };
  const commit = async () => {
    if (!batch) return;
    setBusy(true); setMsg(null);
    try {
      const r = await apiJson<{ created_drafts: number; skipped: { row_number: number; reason: string }[] }>(`${base(institutionId)}/imports/${batch.id}/commit`, "POST", { skip_duplicates: true });
      setResult(r);
      setBatch({ ...batch, status: "committed", committed_count: r.created_drafts });
      setMsg({ kind: "ok", text: t("partner.import.committed", { n: r.created_drafts }) });
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  const preview = batch?.preview ?? [];
  const batchLine = (b: ImportBatch) => <>{b.status} · {tn("common.rows", b.row_count)} · {tn("common.errors", b.error_count)} · {tn("common.duplicates", b.duplicate_count)} · {tn("common.drafts", b.committed_count)}</>;
  return (
    <div className="space-y-6">
      <div><p className="eyebrow">{t("partner.import.eyebrow")}</p><h1 className="mt-1 text-[length:var(--text-h1)]">{t("partner.import.title")}</h1>
        <p className="mt-1 text-sm text-ink-2">{t("partner.import.lede")} <a href="/partner-import-template.csv" className="underline" download>partner-import-template.csv</a> · {t("partner.import.contract")} <a href="/api-docs" className="underline">{t("common.apiDocs")}</a>.</p></div>
      <form onSubmit={upload} className="card flex flex-wrap items-end gap-3">
        <div><label htmlFor="file" className="field">{t("partner.import.file")}</label><input id="file" name="file" type="file" accept=".csv,.json,text/csv,application/json" className="input" required /></div>
        <button type="submit" className="btn" disabled={busy}>{busy ? t("partner.import.uploading") : t("partner.import.uploadPreview")}</button>
      </form>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {batch && (
        <section className="space-y-4" aria-labelledby="preview-heading">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="preview-heading" className="text-xl">{t("partner.import.preview", { name: batch.filename ?? "" })}</h2>
            <p className="text-sm"><span className="badge">{tn("common.rows", batch.row_count)}</span> <span className={`badge ${batch.error_count ? "badge-danger" : ""}`}>{tn("common.errors", batch.error_count)}</span> <span className={`badge ${batch.duplicate_count ? "badge-physical" : ""}`}>{tn("common.duplicates", batch.duplicate_count)}</span> <span className="badge">{batch.status}</span></p>
          </div>
          <details className="card" open={batch.status === "preview"}>
            <summary className="text-sm font-medium">{t("partner.import.mapping")}</summary>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {batch.canonical_fields.map((f) => (
                <label key={f} className="text-xs"><span className="block text-ink-muted">{f}{f === "title" ? " *" : ""}</span>
                  <select className="input mt-0.5 py-1 text-sm" value={batch.mapping.fields[f] ?? ""} disabled={batch.status !== "preview"} onChange={(e) => remap(f, e.target.value)}>
                    <option value="">{t("partner.import.notMapped")}</option>
                    {batch.mapping.headers.map((h) => <option key={h} value={h}>{h}</option>)}
                  </select>
                </label>
              ))}
            </div>
          </details>
          <div className="overflow-auto">
            <table className="table">
              <thead><tr><th>#</th><th>{t("partner.import.flags")}</th><th>{t("partner.import.title_col")}</th><th>{t("partner.import.creators")}</th><th>{t("partner.import.date")}</th><th>{t("partner.import.type")}</th><th>{t("partner.import.access")}</th><th>{t("partner.import.callNo")}</th></tr></thead>
              <tbody>
                {preview.slice(0, 200).map((r) => (
                  <tr key={r.row_number} className={r.errors.length ? "bg-danger-tint/40" : r.duplicate_of ? "bg-brass-tint/50" : ""}>
                    <td className="tnum">{r.row_number}</td>
                    <td className="text-xs">
                      {r.errors.map((e) => <span key={e} className="badge badge-danger mr-1">{e}</span>)}
                      {r.duplicate_of && <span className="badge badge-physical mr-1">{t("partner.import.duplicateOf", { n: r.duplicate_of })}</span>}
                      {r.warnings.map((w) => <span key={w} className="badge mr-1">{w}</span>)}
                      {!r.errors.length && !r.duplicate_of && !r.warnings.length && <span className="badge badge-ok">{t("common.ok")}</span>}
                    </td>
                    <td>{String(r.values.title ?? "")}</td><td>{String(r.values.creators ?? "")}</td><td className="tnum">{String(r.values.date ?? "")}</td><td>{String(r.values.resource_type ?? "")}</td><td>{String(r.values.access_type ?? "")}</td><td className="tnum">{String(r.values.call_number ?? "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {batch.status === "preview" && <button type="button" className="btn" onClick={commit} disabled={busy || batch.row_count - batch.error_count - batch.duplicate_count <= 0}>{t("partner.import.commit", { n: batch.row_count - batch.error_count - batch.duplicate_count })}</button>}
          {result && result.skipped.length > 0 && (<div className="card text-sm"><p className="eyebrow">{t("partner.import.skipped")}</p><ul className="mt-1 list-disc pl-5">{result.skipped.map((s) => <li key={s.row_number}>{t("partner.import.row", { n: s.row_number, reason: s.reason })}</li>)}</ul></div>)}
        </section>
      )}
      {batches.length > 0 && (
        <section><h2 className="text-lg">{t("partner.import.previous")}</h2>
          <ul className="hairline-list mt-2 text-sm">{batches.map((b) => <li key={b.id} className="py-2"><button type="button" className="underline" onClick={() => apiGet<ImportBatch>(`${base(institutionId)}/imports/${b.id}`).then(setBatch)}>{b.filename ?? b.kind}</button> · {batchLine(b)}</li>)}</ul>
        </section>
      )}
    </div>
  );
}
