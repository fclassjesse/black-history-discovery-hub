"use client";

import { useState } from "react";
import { apiForm } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import type { RecordCard } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { useT } from "@/lib/i18n";

export function FindingAidView({ institutionId }: { institutionId: string }) {
  const { t, tn } = useT();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [created, setCreated] = useState<(RecordCard & { pages: number; chunks: number; file_url: string }) | null>(null);
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    const fd = new FormData(e.currentTarget);
    try {
      const r = await apiForm<RecordCard & { pages: number; chunks: number; file_url: string }>(`${base(institutionId)}/finding-aids`, fd);
      setCreated(r);
      setMsg({ kind: "ok", text: t("partner.findingAid.created", { pages: r.pages, chunks: r.chunks }) });
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-6">
      <div><p className="eyebrow">{t("partner.findingAid.eyebrow")}</p><h1 className="mt-1 text-[length:var(--text-h1)]">{t("partner.findingAid.title")}</h1><p className="mt-1 text-sm text-ink-2">{t("partner.findingAid.lede")}</p></div>
      <form onSubmit={submit} className="card space-y-3">
        <div><label htmlFor="fa-file" className="field">{t("partner.findingAid.file")}</label><input id="fa-file" name="file" type="file" accept="application/pdf,.pdf" className="input" required /></div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label htmlFor="fa-title" className="field">{t("partner.findingAid.titleField")}</label><input id="fa-title" name="title" className="input" /></div>
          <div><label htmlFor="fa-url" className="field">{t("partner.findingAid.url")}</label><input id="fa-url" name="original_url" className="input" placeholder="https://…" /></div>
        </div>
        <div><label htmlFor="fa-desc" className="field">{t("partner.findingAid.description")}</label><textarea id="fa-desc" name="description" className="input" rows={3} /></div>
        <button type="submit" className="btn" disabled={busy}>{busy ? t("partner.findingAid.extracting") : t("partner.findingAid.upload")}</button>
      </form>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {created && <div className="card text-sm"><p className="display text-lg">{created.title}</p><p className="text-ink-muted">{t("status.draft")} · {tn("common.pages", created.pages)} · <a href={created.file_url} className="underline" target="_blank" rel="noreferrer">{t("partner.findingAid.openPdf")}</a></p></div>}
    </div>
  );
}
