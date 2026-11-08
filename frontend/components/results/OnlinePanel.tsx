"use client";

import { useState } from "react";
import { useSelection } from "@/lib/store";
import type { RecordCard } from "@/lib/types";
import { useT } from "@/lib/i18n";

/** Online-only resources, kept apart from physical holdings. Docked = floating over the world; stacked = inside the sheet. */
export function OnlinePanel({ records, docked = true }: { records: RecordCard[]; docked?: boolean }) {
  const { t } = useT();
  const { selectRecord, selectedRecordId } = useSelection();
  const [collapsed, setCollapsed] = useState(docked);
  if (records.length === 0) return null;
  const id = docked ? "online-heading" : "online-heading-stacked";
  return (
    <aside aria-labelledby={id} className={`online-panel ${docked ? "rise-in w-[min(360px,calc(100vw-2*var(--gutter)))]" : ""}`}>
      <div className="flex items-start justify-between gap-3 p-4 pb-2">
        <div>
          <p className="kicker text-cream/70">{t("online.kicker")}</p>
          <h3 id={id} className="display mt-0.5 text-xl">{t("online.title")}</h3>
        </div>
        {docked && <button type="button" className="btn btn-pill-chalk btn-sm" aria-expanded={!collapsed} onClick={() => setCollapsed((c) => !c)}>{collapsed ? t("online.show", { n: records.length }) : t("online.hide")}</button>}
      </div>
      {!collapsed && (
        <ol className={`hairline-list px-4 pb-3 text-sm ${docked ? "drawer-scroll max-h-[min(38vh,420px)]" : ""}`} data-lenis-prevent>
          {records.slice(0, 20).map((r) => (
            <li key={r.id} className={`py-2.5 ${selectedRecordId === r.id ? "-mx-2 rounded-xl bg-cream/15 px-2" : ""}`}>
              <a href={r.digital_url ?? r.original_url} target="_blank" rel="noreferrer" className="block truncate font-medium underline" title={r.title}>{r.title} ↗</a>
              <p className="truncate text-xs text-cream/70">{(r.digital_url ?? r.original_url).replace(/^https?:\/\//, "")}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-cream/85">{r.summary}</p>
              <button type="button" className="mt-1 text-xs underline" onClick={() => selectRecord(r.id, r.institution?.id ?? null)}>{t("online.showInResults")}</button>
            </li>
          ))}
          {records.length > 20 && <li className="py-2 text-xs text-cream/70">{t("online.more", { n: records.length - 20 })}</li>}
        </ol>
      )}
    </aside>
  );
}
