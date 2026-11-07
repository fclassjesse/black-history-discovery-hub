"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiForm, apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import type { Candidate, ScanItem, ShelfScan } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { useFormat, useT } from "@/lib/i18n";

export function ShelfScanView({ institutionId }: { institutionId: string }) {
  const { t, tn } = useT();
  const fmt = useFormat();
  const [scans, setScans] = useState<ShelfScan[]>([]);
  const [scan, setScan] = useState<ShelfScan | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error" | "warn"; text: string } | null>(null);
  const pollRef = useRef<number | null>(null);
  const loadList = useCallback(() => apiGet<{ scans: ShelfScan[] }>(`${base(institutionId)}/shelf-scans`).then((d) => setScans(d.scans)).catch(() => {}), [institutionId]);
  useEffect(() => { loadList(); }, [loadList]);
  const refresh = useCallback(async (id: string) => { const s = await apiGet<ShelfScan>(`${base(institutionId)}/shelf-scans/${id}`); setScan(s); return s; }, [institutionId]);
  useEffect(() => {
    if (!scan || (scan.status !== "queued" && scan.status !== "processing")) return;
    pollRef.current = window.setTimeout(() => refresh(scan.id), 2000);
    return () => { if (pollRef.current) window.clearTimeout(pollRef.current); };
  }, [scan, refresh]);

  const upload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const file = (e.currentTarget.elements.namedItem("image") as HTMLInputElement).files?.[0];
    if (!file) return;
    setBusy(true); setMsg(null);
    const fd = new FormData(); fd.append("image", file);
    try {
      const s = await apiForm<ShelfScan>(`${base(institutionId)}/shelf-scans`, fd);
      setScan(s);
      loadList();
      if (s.status === "failed") setMsg({ kind: "error", text: s.error ?? t("partner.scan.failed") });
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-6">
      <div><p className="eyebrow">{t("partner.scan.eyebrow")}</p><h1 className="mt-1 text-[length:var(--text-h1)]">{t("partner.scan.title")}</h1>
        <p className="mt-1 text-sm text-ink-2">{t("partner.scan.lede1")}<strong>{t("partner.scan.you")}</strong>{t("partner.scan.lede2")}<em>{t("partner.scan.draft")}</em>{t("partner.scan.lede3")}</p></div>
      <form onSubmit={upload} className="card flex flex-wrap items-end gap-3">
        <div><label htmlFor="image" className="field">{t("partner.scan.photo")}</label><input id="image" name="image" type="file" accept="image/*" capture="environment" className="input" required /></div>
        <button type="submit" className="btn" disabled={busy}>{busy ? t("partner.scan.reading") : t("partner.scan.upload")}</button>
      </form>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {scan && <ScanReview institutionId={institutionId} scan={scan} onChange={(s) => { setScan(s); loadList(); }} />}
      {scans.length > 0 && (
        <section><h2 className="text-lg">{t("partner.scan.previous")}</h2>
          <ul className="hairline-list mt-2 text-sm">{scans.map((s) => <li key={s.id} className="py-2"><button type="button" className="underline" onClick={() => refresh(s.id)}>{fmt.dateTime(s.created_at)}</button> · {s.status} · {tn("common.items", s.items?.length ?? 0)}{s.error ? <span className="text-danger"> · {s.error}</span> : ""}</li>)}</ul>
        </section>
      )}
    </div>
  );
}

function ScanReview({ institutionId, scan, onChange }: { institutionId: string; scan: ShelfScan; onChange: (s: ShelfScan) => void }) {
  const { t } = useT();
  return (
    <section className="space-y-4" aria-labelledby="scan-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="scan-heading" className="text-xl">{t("partner.scan.scan")} · <span className="badge">{scan.status}</span>{scan.model && <span className="ml-2 text-xs text-ink-muted">{t("partner.scan.vision", { model: scan.model })}</span>}</h2>
        <a href={scan.image_url} target="_blank" rel="noreferrer" className="text-sm underline">{t("partner.scan.openPhoto")}</a>
      </div>
      {(scan.status === "queued" || scan.status === "processing") && <p className="text-sm text-ink-muted" role="status">{t("partner.scan.working")}</p>}
      {scan.status === "failed" && <Notice kind="error">{scan.error}</Notice>}
      {scan.error && scan.status !== "failed" && <Notice kind="warn">{scan.error}</Notice>}
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={scan.image_url} alt={t("partner.scan.photoAlt")} className="w-full border border-rule object-contain" />
        <ol className="space-y-3">{(scan.items ?? []).map((it) => <ItemCard key={it.id} institutionId={institutionId} scanId={scan.id} item={it} onChange={async () => onChange(await apiGet<ShelfScan>(`${base(institutionId)}/shelf-scans/${scan.id}`))} />)}</ol>
      </div>
    </section>
  );
}

function ItemCard({ institutionId, scanId, item, onChange }: { institutionId: string; scanId: string; item: ScanItem; onChange: () => void }) {
  const { t } = useT();
  const [title, setTitle] = useState(item.proposed_title ?? "");
  const [author, setAuthor] = useState(item.proposed_author ?? "");
  const [isbn, setIsbn] = useState(item.proposed_isbn ?? "");
  const [choice, setChoice] = useState<string>(item.selected_candidate?.openlibrary_work_key ?? "");
  const [callNo, setCallNo] = useState(item.call_number ?? "");
  const [shelf, setShelf] = useState(item.shelf_label ?? "");
  const [edition, setEdition] = useState("");
  const [holds, setHolds] = useState(item.confirmed_holding);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const url = `${base(institutionId)}/shelf-scans/${scanId}/items/${item.id}`;
  const candidate: Candidate | null = choice === "manual" ? null : item.candidates.find((c) => c.openlibrary_work_key === choice) ?? null;
  const refreshCandidates = async () => {
    setBusy(true); setErr(null);
    try { await apiJson(url, "PATCH", { proposed_title: title || null, proposed_author: author || null, proposed_isbn: isbn || null, refresh_candidates: true }); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const confirm = async () => {
    setBusy(true); setErr(null);
    try {
      await apiJson(`${url}/confirm`, "POST", { confirmed_holding: holds, selected_candidate: candidate, manual_title: choice === "manual" || !candidate ? title || null : null, manual_author: choice === "manual" || !candidate ? author || null : null, call_number: callNo || null, shelf_label: shelf || null, edition_note: edition || null });
      onChange();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const reject = async () => { setBusy(true); try { await apiJson(`${url}/reject`, "POST"); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } };
  const done = item.status !== "proposed";
  return (
    <li className={`card ${done ? "opacity-80" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><p className="eyebrow">{t("partner.scan.book", { n: item.position + 1 })}</p><p className="display text-lg">{item.spine_text ?? t("partner.scan.noText")}</p></div>
        <div className="text-right text-xs"><span className="badge">{item.status}</span><p className="tnum mt-1 text-ink-muted">{t("partner.scan.confidence", { n: item.confidence != null ? Math.round(item.confidence * 100) : "?" })}</p></div>
      </div>
      {item.uncertainties.length > 0 && <p className="mt-1 text-xs text-ink-2"><strong>{t("partner.scan.uncertainties")}</strong> {item.uncertainties.join("; ")}</p>}
      {done ? (
        <p className="mt-2 text-sm">{item.status === "confirmed" ? <>{t("partner.scan.confirmed")}{item.call_number ? ` · ${t("common.callNo", { n: item.call_number })}` : ""}. {t("partner.scan.publishFrom")}</> : t("partner.scan.rejected")}</p>
      ) : (
        <div className="mt-3 space-y-3">
          <div className="grid gap-2 sm:grid-cols-3">
            <div><label htmlFor={`t-${item.id}`} className="field">{t("partner.scan.titleRead")}</label><input id={`t-${item.id}`} className="input py-1" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div><label htmlFor={`a-${item.id}`} className="field">{t("partner.scan.authorRead")}</label><input id={`a-${item.id}`} className="input py-1" value={author} onChange={(e) => setAuthor(e.target.value)} /></div>
            <div><label htmlFor={`i-${item.id}`} className="field">{t("partner.scan.isbn")}</label><input id={`i-${item.id}`} className="input tnum py-1" value={isbn} onChange={(e) => setIsbn(e.target.value)} /></div>
          </div>
          <button type="button" className="btn btn-secondary text-xs" onClick={refreshCandidates} disabled={busy}>{t("partner.scan.lookupAgain")}</button>
          <fieldset>
            <legend className="field">{t("partner.scan.candidates")}</legend>
            <ul className="space-y-1">
              {item.candidates.map((c) => (
                <li key={c.openlibrary_work_key}>
                  <label className="flex cursor-pointer items-start gap-2 text-sm">
                    <input type="radio" name={`cand-${item.id}`} className="mt-1" checked={choice === c.openlibrary_work_key} onChange={() => setChoice(c.openlibrary_work_key)} />
                    <span><strong>{c.title}</strong> — {c.authors.join(", ") || t("partner.scan.authorUnknown")}{c.first_publish_year ? ` (${c.first_publish_year})` : ""} · {t("partner.scan.editions", { n: c.edition_count ?? "?" })} · <span className="tnum">{t("partner.scan.match", { n: Math.round(c.score * 100) })}</span> {c.openlibrary_url && <a href={c.openlibrary_url} className="underline" target="_blank" rel="noreferrer">{t("partner.scan.view")}</a>}</span>
                  </label>
                </li>
              ))}
              <li><label className="flex cursor-pointer items-center gap-2 text-sm"><input type="radio" name={`cand-${item.id}`} checked={choice === "manual"} onChange={() => setChoice("manual")} />{t("partner.scan.noneOfThese")}</label></li>
            </ul>
            {item.candidates.length === 0 && <p className="text-xs text-ink-muted">{t("partner.scan.noCandidates")}</p>}
          </fieldset>
          <div className="grid gap-2 sm:grid-cols-3">
            <div><label htmlFor={`e-${item.id}`} className="field">{t("partner.scan.edition")}</label><input id={`e-${item.id}`} className="input py-1" value={edition} onChange={(e) => setEdition(e.target.value)} placeholder={t("partner.scan.editionPlaceholder")} /></div>
            <div><label htmlFor={`c-${item.id}`} className="field">{t("partner.scan.callNumber")}</label><input id={`c-${item.id}`} className="input tnum py-1" value={callNo} onChange={(e) => setCallNo(e.target.value)} /></div>
            <div><label htmlFor={`s-${item.id}`} className="field">{t("partner.scan.shelf")}</label><input id={`s-${item.id}`} className="input py-1" value={shelf} onChange={(e) => setShelf(e.target.value)} /></div>
          </div>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="checkbox mt-0.5" checked={holds} onChange={(e) => setHolds(e.target.checked)} /><span><strong>{t("partner.scan.holds")}</strong> {t("partner.scan.holdsNote")}</span></label>
          {err && <Notice kind="error">{err}</Notice>}
          <div className="flex gap-2"><button type="button" className="btn" onClick={confirm} disabled={busy || !holds || (!candidate && !title)}>{t("partner.scan.confirm")}</button><button type="button" className="btn btn-danger" onClick={reject} disabled={busy}>{t("partner.scan.reject")}</button></div>
        </div>
      )}
    </li>
  );
}
