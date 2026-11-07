"use client";

import type { InstitutionCard } from "@/lib/types";
import { Stamp } from "@/components/art/Stamps";
import { useLabels } from "@/lib/labels";
import { useTilt } from "@/lib/motion";
import { Link, useT } from "@/lib/i18n";

const TONES = ["plate-ochre", "plate-sun", "plate-rose", "plate-moss", "plate-cream", "plate-ink"] as const;

export function tileTone(i: number) { return TONES[i % TONES.length]; }

/** A poster-like tile for one institution: flat colour, halftone, stamp illustration, slab title. */
export function InstitutionTile({ inst, index, className = "" }: { inst: InstitutionCard; index: number; className?: string }) {
  const { t, tn } = useT();
  const L = useLabels();
  const ref = useTilt<HTMLAnchorElement>(7, 900);
  const tone = tileTone(index);
  const dark = tone === "plate-moss" || tone === "plate-ink";
  return (
    <Link ref={ref} href={`/institutions/${inst.slug}`} data-reveal-child className={`tilt ${tone} halftone group relative flex aspect-[4/5] w-[min(78vw,300px)] flex-col justify-between overflow-hidden p-5 no-underline ${className}`}>
      <div className="flex items-start justify-between gap-2">
        <span className={`badge ${dark ? "badge-verified" : ""}`}>{L.kind(inst.kind)}</span>
        <span className={`tnum text-xs ${dark ? "text-cream/80" : "text-ink/70"}`}>{tn("common.records", inst.published_records ?? 0)}</span>
      </div>
      <Stamp kind={inst.kind} className="mx-auto w-[62%] transition-transform duration-500 [transition-timing-function:var(--ease-bounce)] group-hover:-translate-y-2 group-hover:rotate-[-4deg] group-hover:scale-105" style={{ transform: "translateZ(40px)" }} />
      <div style={{ transform: "translateZ(24px)" }}>
        <p className={`display text-[1.35rem] leading-tight ${dark ? "text-cream" : "text-ink"}`}>{inst.name}</p>
        <p className={`mt-1 text-sm ${dark ? "text-cream/80" : "text-ink/75"}`}>{[inst.city, inst.region].filter(Boolean).join(", ") || inst.country || t("common.online")}</p>
        <p className={`mt-2 text-[0.72rem] ${dark ? "text-cream/70" : "text-ink/60"}`}>{L.precision(inst.location_precision)}{inst.partner_status === "demo" ? ` · ${t("common.sampleData")}` : inst.partner_status === "partner" ? ` · ${t("common.partner")}` : ""}</p>
      </div>
      <span className={`absolute right-4 top-12 grid h-10 w-10 place-items-center rounded-full border-2 text-lg transition-transform duration-500 [transition-timing-function:var(--ease-bounce)] group-hover:rotate-[-20deg] group-hover:scale-110 ${dark ? "border-cream text-cream" : "border-ink text-ink"}`} aria-hidden>→</span>
    </Link>
  );
}
