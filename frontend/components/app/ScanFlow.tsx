"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiForm, apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import { useAppSession } from "@/lib/appSession";
import { character } from "@/lib/character";
import type { Candidate, ScanItem, ShelfScan } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { AppHeader } from "@/components/app/AppHeader";
import { CameraIcon, CheckIcon, CrossIcon, FileIcon } from "@/components/app/AppIcons";
import { useFormat, useT } from "@/lib/i18n";

/** Shelf camera: photo → vision proposes books → Open Library candidates → you confirm → draft. */
export function ScanFlow() {
  const { t, tn } = useT();
  const fmt = useFormat();
  const { membership } = useAppSession();
  const root = base(membership.institution_id);
  const [scans, setScans] = useState<ShelfScan[]>([]);
  const [scan, setScan] = useState<ShelfScan | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error" | "warn"; text: string } | null>(null);
  const pollRef = useRef<number | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);

  const loadList = useCallback(() => apiGet<{ scans: ShelfScan[] }>(`${root}/shelf-scans`).then((d) => setScans(d.scans)).catch(() => {}), [root]);
  useEffect(() => { loadList(); }, [loadList]);
  const refresh = useCallback(async (id: string) => { const s = await apiGet<ShelfScan>(`${root}/shelf-scans/${id}`); setScan(s); return s; }, [root]);

  // poll while the vision job runs; Nova thinks along
  const working = scan?.status === "queued" || scan?.status === "processing";
  useEffect(() => {
    if (!scan) return;
    if (working) { character.set("thinking", undefined, 60000); pollRef.current = window.setTimeout(() => refresh(scan.id), 2000); }
    else if (scan.status === "failed") character.set("abstain");
    else character.set("celebrate");
    return () => { if (pollRef.current) window.clearTimeout(pollRef.current); };
  }, [scan, working, refresh]);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setMsg(null);
    const fd = new FormData(); fd.append("image", file);
    try {
      const s = await apiForm<ShelfScan>(`${root}/shelf-scans`, fd);
      setScan(s);
      loadList();
      if (s.status === "failed") setMsg({ kind: "error", text: s.error ?? t("app.scan.failed") });
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); character.set("abstain"); } finally { setBusy(false); }
  };
  const items = scan?.items ?? [];
  const open = items.filter((i) => i.status === "proposed").length;

  return (
    <div className="app-screen">
      <AppHeader eyebrow={t("app.scan.eyebrow")} title={t("app.scan.title")} line={t("app.scan.line")} />
      <div className="grid gap-2">
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => upload(e.target.files?.[0])} />
        <input ref={libraryRef} type="file" accept="image/*" className="sr-only" onChange={(e) => upload(e.target.files?.[0])} />
        <button type="button" className="big-action" disabled={busy} onClick={() => cameraRef.current?.click()}><CameraIcon /> {busy ? t("app.scan.uploading") : t("app.scan.takePhoto")}</button>
        <button type="button" className="big-action secondary" disabled={busy} onClick={() => libraryRef.current?.click()}><FileIcon /> {t("app.scan.chooseLibrary")}</button>
      </div>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}

      {scan && (
        <section aria-labelledby="scan-h" className="grid gap-3">
          <div className="tile flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={scan.image_url} alt={t("app.scan.photoAlt")} className="h-20 w-20 shrink-0 rounded-xl object-cover" />
            <div className="min-w-0 flex-1">
              <h2 id="scan-h" className="display text-lg leading-tight">{working ? t("app.scan.reading") : scan.status === "failed" ? t("app.scan.couldNotRead") : tn("app.scan.found", items.length)}</h2>
              <p className="text-xs text-ink-muted">{working ? t("app.scan.refreshes") : scan.model ? t("app.scan.vision", { model: scan.model }) : ""}{!working && open > 0 ? t("app.scan.toConfirm", { n: open }) : ""}</p>
              {working && <span className="mt-2 inline-flex gap-1" aria-hidden><span className="think-dot inline-block h-2 w-2 rounded-full bg-ink" /><span className="think-dot inline-block h-2 w-2 rounded-full bg-ink" /><span className="think-dot inline-block h-2 w-2 rounded-full bg-ink" /></span>}
            </div>
          </div>
          {scan.status === "failed" && <Notice kind="error">{scan.error}</Notice>}
          {scan.error && scan.status !== "failed" && <Notice kind="warn">{scan.error}</Notice>}
          <ol className="grid gap-3">
            {items.map((it) => <ScanItemCard key={it.id} url={`${root}/shelf-scans/${scan.id}/items/${it.id}`} item={it} onChange={() => refresh(scan.id)} />)}
          </ol>
        </section>
      )}

      {scans.length > 0 && (
        <section className="tile">
          <h2 className="kicker text-ink-muted">{t("app.scan.previous")}</h2>
          <ul className="hairline-list mt-1 text-sm">
            {scans.slice(0, 8).map((s) => (
              <li key={s.id}>
                <button type="button" className="flex w-full items-center justify-between py-2 text-left" onClick={() => refresh(s.id)}>
                  <span>{fmt.date(s.created_at)} <span className="text-ink-muted">· {tn("common.items", s.items?.length ?? 0)}</span></span>
                  <span className="badge">{s.status}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ScanItemCard({ url, item, onChange }: { url: string; item: ScanItem; onChange: () => void }) {
  const { t } = useT();
  const [title, setTitle] = useState(item.proposed_title ?? "");
  const [author, setAuthor] = useState(item.proposed_author ?? "");
  const [choice, setChoice] = useState<string>(item.selected_candidate?.openlibrary_work_key ?? item.candidates[0]?.openlibrary_work_key ?? "manual");
  const [callNo, setCallNo] = useState(item.call_number ?? "");
  const [holds, setHolds] = useState(item.confirmed_holding);
  const [more, setMore] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const candidate: Candidate | null = choice === "manual" ? null : item.candidates.find((c) => c.openlibrary_work_key === choice) ?? null;
  const conf = item.confidence != null ? Math.round(item.confidence * 100) : null;
  const level = conf == null ? "mid" : conf < 45 ? "low" : conf < 75 ? "mid" : "high";

  const lookup = async () => {
    setBusy(true); setErr(null);
    try { await apiJson(url, "PATCH", { proposed_title: title || null, proposed_author: author || null, refresh_candidates: true }); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const confirm = async () => {
    setBusy(true); setErr(null);
    try {
      await apiJson(`${url}/confirm`, "POST", { confirmed_holding: holds, selected_candidate: candidate, manual_title: candidate ? null : title || null, manual_author: candidate ? null : author || null, call_number: callNo || null, shelf_label: null, edition_note: null });
      character.set("celebrate");
      onChange();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const reject = async () => { setBusy(true); try { await apiJson(`${url}/reject`, "POST"); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } };
  const done = item.status !== "proposed";

  return (
    <li className={`tile ${done ? "opacity-75" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="kicker text-ink-muted">{t("app.scan.book", { n: item.position + 1 })}</p>
          <p className="display text-lg leading-tight">{item.spine_text ?? t("app.scan.noText")}</p>
        </div>
        <span className="badge shrink-0">{item.status}</span>
      </div>
      {conf != null && (
        <div className="mt-2 flex items-center gap-2 text-xs text-ink-muted"><div className="meter flex-1" data-level={level}><span style={{ width: `${conf}%` }} /></div><span className="tnum">{t("app.scan.sure", { n: conf })}</span></div>
      )}
      {item.uncertainties.length > 0 && <p className="mt-1 text-xs text-ink-2">{item.uncertainties.join("; ")}</p>}
      {done ? (
        <p className="mt-3 text-sm">{item.status === "confirmed" ? <>{t("app.scan.draftCreated")}{item.call_number ? ` · ${t("common.callNo", { n: item.call_number })}` : ""}. {t("app.scan.publishFrom1")}<strong>{t("app.tabs.review")}</strong>{t("app.scan.publishFrom2")}</> : t("app.scan.rejected")}</p>
      ) : (
        <div className="mt-3 grid gap-3">
          <fieldset className="grid gap-1.5">
            <legend className="field">{t("app.scan.which")}</legend>
            {item.candidates.slice(0, 4).map((c) => (
              <label key={c.openlibrary_work_key} className="cand" data-on={choice === c.openlibrary_work_key}>
                <input type="radio" className="mt-1" name={`cand-${item.id}`} checked={choice === c.openlibrary_work_key} onChange={() => setChoice(c.openlibrary_work_key)} />
                <span className="min-w-0 text-sm"><strong className="block leading-tight">{c.title}</strong><span className="text-ink-2">{c.authors.join(", ") || t("app.scan.authorUnknown")}{c.first_publish_year ? ` · ${c.first_publish_year}` : ""}</span><span className="tnum block text-xs text-ink-muted">{t("app.scan.match", { n: Math.round(c.score * 100) })}</span></span>
              </label>
            ))}
            <label className="cand" data-on={choice === "manual"}>
              <input type="radio" className="mt-1" name={`cand-${item.id}`} checked={choice === "manual"} onChange={() => { setChoice("manual"); setMore(true); }} />
              <span className="text-sm">{t("app.scan.noneOfThese")}</span>
            </label>
          </fieldset>
          <button type="button" className="text-left text-sm underline" onClick={() => setMore((m) => !m)}>{more ? t("app.scan.hideDetails") : t("app.scan.editDetails")}</button>
          {more && (
            <div className="grid gap-2">
              <div><label htmlFor={`t-${item.id}`} className="field">{t("app.scan.titleField")}</label><input id={`t-${item.id}`} className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
              <div><label htmlFor={`a-${item.id}`} className="field">{t("app.scan.author")}</label><input id={`a-${item.id}`} className="input" value={author} onChange={(e) => setAuthor(e.target.value)} /></div>
              <div><label htmlFor={`c-${item.id}`} className="field">{t("app.scan.callNumber")}</label><input id={`c-${item.id}`} className="input tnum" value={callNo} onChange={(e) => setCallNo(e.target.value)} /></div>
              <button type="button" className="btn btn-secondary btn-sm justify-self-start" onClick={lookup} disabled={busy}>{t("app.scan.lookupAgain")}</button>
            </div>
          )}
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="checkbox mt-0.5" checked={holds} onChange={(e) => setHolds(e.target.checked)} /><span><strong>{t("app.scan.holds")}</strong></span></label>
          {err && <Notice kind="error">{err}</Notice>}
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <button type="button" className="btn" onClick={confirm} disabled={busy || !holds || (!candidate && !title)}><CheckIcon /> {t("app.scan.confirm")}</button>
            <button type="button" className="btn btn-danger btn-icon" aria-label={t("app.scan.rejectAria")} onClick={reject} disabled={busy}><CrossIcon /></button>
          </div>
        </div>
      )}
    </li>
  );
}
