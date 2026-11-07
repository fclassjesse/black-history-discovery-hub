"use client";

import type { Pin, RecordCard } from "@/lib/types";
import { pinKind, useLabels } from "@/lib/labels";
import { Link, useFormat, useT } from "@/lib/i18n";

interface Props {
  pin: Pin;
  recordsById: Map<string, RecordCard>;
  open: boolean;
  hovered: boolean;
  mode: "idle" | "results";
  /** Position in the current batch; staggers the pop-in. */
  order?: number;
  onToggle: () => void;
}

/** A cartoon pin with a count, hover label and an anchored card with holdings. Rendered through a portal into a MapLibre marker. */
export function PinMarker({ pin, recordsById, open, hovered, mode, order = 0, onToggle }: Props) {
  const { t } = useT();
  const L = useLabels();
  const fmt = useFormat();
  const inst = pin.institution;
  const kind = pinKind(inst.location_precision, recordsById.get(pin.record_ids[0] ?? "")?.holding_verification);
  const shown = pin.record_ids.slice(0, 4).map((id) => recordsById.get(id)).filter((r): r is RecordCard => Boolean(r));
  const unit = mode === "idle" ? t("world.recordsIndexed") : pin.count === 1 ? t("world.holding_one") : t("world.holding_other");
  const count = fmt.number(pin.count);
  return (
    <div className="pin" data-open={open} data-hover={hovered}>
      {open && (
        <div className="pin-card" role="group" aria-label={`${inst.name}: ${count} ${unit}`}>
          <p className="kicker text-ink-muted">{L.kind(inst.kind)} · {L.precision(inst.location_precision)}</p>
          <p className="display mt-1 text-[1.05rem] leading-tight">{inst.name}</p>
          <p className="mt-0.5 text-xs text-ink-muted">{[inst.city, inst.region].filter(Boolean).join(", ")} · <span className="tnum">{count}</span> {unit}</p>
          {shown.length > 0 && (
            <ul className="hairline-list mt-2">
              {shown.map((r) => (
                <li key={r.id} className="py-1.5">
                  <a href={`#record-${r.id}`} className="block truncate font-medium underline" title={r.title}>{r.title}</a>
                  {r.call_number && <span className="tnum text-[0.7rem] text-ink-muted">{t("common.callNoCap", { n: r.call_number })}</span>}
                </li>
              ))}
            </ul>
          )}
          {pin.record_ids.length > shown.length && <p className="mt-1 text-[0.72rem] text-ink-muted">{t("world.moreInList", { n: pin.record_ids.length - shown.length })}</p>}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Link href={`/institutions/${inst.slug}`} className="btn btn-sm">{t("common.visitRequest")}</Link>
            {mode === "idle" && <Link href={`/?institution=${inst.slug}`} className="btn btn-sm btn-secondary">{t("world.exploreHoldings")}</Link>}
          </div>
        </div>
      )}
      <button type="button" className="pin-body" style={{ "--pop-delay": `${Math.min(order, 14) * 70}ms` } as React.CSSProperties} aria-expanded={open} aria-label={`${inst.name}, ${count} ${unit}, ${L.precision(inst.location_precision)}`} onClick={(e) => { e.stopPropagation(); onToggle(); }}>
        <span className="pin-head" data-kind={kind} data-empty={pin.count === 0}><span className="tnum">{pin.count === 0 ? "" : pin.count > 99 ? "99+" : pin.count}</span></span>
        <span className="pin-shadow" />
      </button>
      <span className="pin-label">{inst.name}</span>
    </div>
  );
}
