"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api";
import { base } from "@/components/partner/usePartner";
import { useAppSession } from "@/lib/appSession";
import { character } from "@/lib/character";
import type { RecordCard, ReviewStatus } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { AccessBadge, StatusBadge } from "@/components/ui/Badges";
import { AppHeader } from "@/components/app/AppHeader";
import { Link, useFormat, useT } from "@/lib/i18n";
import { useLabels } from "@/lib/labels";

interface ListResp { total: number; results: RecordCard[]; role: string; actions: Record<string, boolean> }
const ACTIONS: [string, string][] = [["publish", ""], ["submit", "btn-secondary"], ["return", "btn-secondary"], ["withdraw", "btn-danger"], ["reopen", "btn-secondary"]];
const FROM: Record<string, ReviewStatus[]> = { submit: ["draft"], return: ["in_review"], publish: ["draft", "in_review"], withdraw: ["published", "in_review"], reopen: ["withdrawn"] };
const SEGMENTS = ["draft", "in_review", "published", "withdrawn", ""] as const;

export function ReviewQueue() {
  const { t, locale } = useT();
  const L = useLabels();
  const fmt = useFormat();
  const { membership } = useAppSession();
  const sp = useSearchParams();
  const [status, setStatus] = useState<string>(sp.get("status") ?? "draft");
  const [q, setQ] = useState("");
  const [data, setData] = useState<ListResp | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const load = useCallback(() => apiGet<ListResp>(`${base(membership.institution_id)}/records?page_size=100${status ? `&status=${status}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`).then(setData).catch((e) => setMsg({ kind: "error", text: e.message })), [membership.institution_id, status, q]);
  useEffect(() => { load(); }, [load, locale]);
  const act = async (r: RecordCard, action: string) => {
    setMsg(null);
    try {
      await apiJson(`${base(membership.institution_id)}/records/${r.id}/${action}`, "POST", { note: null });
      setMsg({ kind: "ok", text: action === "publish" ? t("app.review.onWorld", { title: r.title }) : action === "withdraw" ? t("app.review.leftPublic", { title: r.title }) : t("app.review.done", { action: t(`app.review.actions.${action}`) }) });
      character.set(action === "publish" ? "celebrate" : "idle");
      load();
    } catch (err) { setMsg({ kind: "error", text: (err as Error).message }); }
  };
  return (
    <div className="app-screen">
      <AppHeader eyebrow={t("app.review.eyebrow")} title={t("app.review.title")} line={t("app.review.line")} />
      <div className="seg" role="tablist" aria-label={t("app.review.statusAria")}>{SEGMENTS.map((v) => <button key={v} type="button" role="tab" aria-selected={status === v} onClick={() => setStatus(v)}>{t(`app.review.segments.${v}`)}</button>)}</div>
      <div><label htmlFor="rq" className="sr-only">{t("app.review.searchLabel")}</label><input id="rq" className="input" placeholder={t("app.review.searchPlaceholder")} value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
      {!data ? <p className="text-sm text-ink-muted">{t("common.loading")}</p> : data.results.length === 0 ? <Notice>{status ? t("app.review.nothingStatus", { status: L.status(status) }) : t("app.review.nothingHere")}</Notice> : (
        <ul className="grid gap-3">
          {data.results.map((r) => (
            <li key={r.id} className="tile">
              <div className="flex flex-wrap gap-1"><StatusBadge status={r.review_status} /><AccessBadge access={r.access_type} /></div>
              <h2 className="mt-2 text-[1.15rem] leading-snug">{r.title}</h2>
              <p className="mt-1 text-sm text-ink-2">{[r.creators.slice(0, 2).join("; "), r.date_text, L.resourceType(r.resource_type), r.call_number ? t("common.callNo", { n: r.call_number }) : ""].filter(Boolean).join(" · ")}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {ACTIONS.filter(([a]) => data.actions[a] && FROM[a].includes(r.review_status)).map(([a, cls]) => <button key={a} type="button" className={`btn btn-sm ${cls}`} onClick={() => act(r, a)}>{t(`app.review.actions.${a}`)}</button>)}
                {r.review_status === "published" && <Link href={`/records/${r.id}`} className="btn btn-quiet btn-sm">{t("app.review.publicPage")}</Link>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {data && <p className="text-center text-xs text-ink-muted">{t("app.review.total", { n: fmt.number(data.total), role: L.role(data.role) })}</p>}
    </div>
  );
}
