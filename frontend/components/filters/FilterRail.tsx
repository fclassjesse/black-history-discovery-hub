"use client";

import type { Facet } from "@/lib/types";
import { useLabels } from "@/lib/labels";
import { useT } from "@/lib/i18n";

export interface FilterState {
  types: string[];
  access: string[];
  institution: string[];
  lang: string[];
  verification: string[];
  rights: string[];
  country: string[];
  people: string[];
  places: string[];
  communities: string[];
  date_from: string;
  date_to: string;
}

export const EMPTY_FILTERS: FilterState = { types: [], access: [], institution: [], lang: [], verification: [], rights: [], country: [], people: [], places: [], communities: [], date_from: "", date_to: "" };

export function countActive(value: FilterState): number {
  return Object.values(value).reduce<number>((n, v) => n + (Array.isArray(v) ? v.length : v ? 1 : 0), 0);
}

interface Props {
  facets: Record<string, Facet[]>;
  value: FilterState;
  onChange: (next: FilterState) => void;
  unknownLocationCount: number;
}

function Chip({ checked, label, count, onToggle }: { checked: boolean; label: string; count?: number; onToggle: () => void }) {
  return (
    <label className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border-[1.5px] px-3 py-1 text-sm transition-colors ${checked ? "border-ink bg-ink text-cream" : "border-ink/30 bg-white text-ink hover:border-ink"}`}>
      <input type="checkbox" className="sr-only" checked={checked} onChange={onToggle} />
      <span>{label}</span>
      {count != null && <span className={`tnum text-xs ${checked ? "text-cream/70" : "text-ink-muted"}`}>{count}</span>}
    </label>
  );
}

function Group({ title, options, selected, onToggle, labelFor }: { title: string; options: Facet[]; selected: string[]; onToggle: (v: string) => void; labelFor?: (v: string) => string }) {
  if (options.length === 0) return null;
  return (
    <fieldset>
      <legend className="kicker mb-2 text-ink-muted">{title}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => <Chip key={o.value} checked={selected.includes(o.value)} label={labelFor ? labelFor(o.value) : o.label} count={o.count} onToggle={() => onToggle(o.value)} />)}
      </div>
    </fieldset>
  );
}

export function FilterRail({ facets, value, onChange, unknownLocationCount }: Props) {
  const { t, tn } = useT();
  const L = useLabels();
  const toggle = (key: keyof FilterState) => (v: string) => {
    const cur = value[key] as string[];
    onChange({ ...value, [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] });
  };
  const active = countActive(value);
  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xl">{t("filters.title")}</h2>
        {active > 0 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => onChange(EMPTY_FILTERS)}>{t("filters.clear", { n: active })}</button>}
      </div>
      <fieldset>
        <legend className="kicker mb-2 text-ink-muted">{t("filters.access")}</legend>
        <div className="flex flex-wrap gap-1.5">
          <Chip checked={value.access.includes("online")} label={t("filters.online")} onToggle={() => toggle("access")("online")} />
          <Chip checked={value.access.includes("physical")} label={t("filters.physical")} onToggle={() => toggle("access")("physical")} />
        </div>
      </fieldset>
      <fieldset>
        <legend className="kicker mb-2 text-ink-muted">{t("filters.dateRange")}</legend>
        <div className="flex items-center gap-2 text-sm">
          <label className="sr-only" htmlFor="date_from">{t("filters.fromYear")}</label>
          <input id="date_from" className="input tnum w-24" inputMode="numeric" placeholder={t("filters.from")} value={value.date_from} onChange={(e) => onChange({ ...value, date_from: e.target.value.replace(/\D/g, "").slice(0, 4) })} />
          <span aria-hidden>–</span>
          <label className="sr-only" htmlFor="date_to">{t("filters.toYear")}</label>
          <input id="date_to" className="input tnum w-24" inputMode="numeric" placeholder={t("filters.to")} value={value.date_to} onChange={(e) => onChange({ ...value, date_to: e.target.value.replace(/\D/g, "").slice(0, 4) })} />
        </div>
      </fieldset>
      <fieldset>
        <legend className="kicker mb-2 text-ink-muted">{t("filters.heldIn")}</legend>
        <div className="flex flex-wrap gap-1.5">
          <Chip checked={value.country.includes("Canada")} label={t("filters.heldInCanada")} count={(facets.country ?? []).find((f) => f.value === "Canada")?.count} onToggle={() => toggle("country")("Canada")} />
          {(facets.country ?? []).filter((f) => f.value !== "Canada").map((f) => (
            <Chip key={f.value} checked={value.country.includes(f.value)} label={f.label ?? f.value} count={f.count} onToggle={() => toggle("country")(f.value)} />
          ))}
        </div>
        <p className="mt-1 text-xs text-ink-muted">{t("filters.countryNote")}</p>
      </fieldset>
      <Group title={t("filters.communities")} options={facets.communities ?? []} selected={value.communities} onToggle={toggle("communities")} />
      <Group title={t("filters.people")} options={facets.people ?? []} selected={value.people} onToggle={toggle("people")} />
      <Group title={t("filters.places")} options={facets.places ?? []} selected={value.places} onToggle={toggle("places")} />
      <Group title={t("filters.resourceType")} options={facets.resource_type ?? []} selected={value.types} onToggle={toggle("types")} labelFor={(v) => L.resourceType(v)} />
      <Group title={t("filters.institution")} options={facets.institution ?? []} selected={value.institution} onToggle={toggle("institution")} />
      <Group title={t("filters.verification")} options={facets.holding_verification ?? []} selected={value.verification} onToggle={toggle("verification")} labelFor={(v) => L.verification(v)} />
      <Group title={t("filters.language")} options={facets.language ?? []} selected={value.lang} onToggle={toggle("lang")} labelFor={(v) => L.language(v) || (facets.language ?? []).find((f) => f.value === v)?.label || v} />
      <Group title={t("filters.rights")} options={facets.rights_status ?? []} selected={value.rights} onToggle={toggle("rights")} labelFor={(v) => L.rights(v)} />
      {unknownLocationCount > 0 && (
        <p className="rule pt-3 text-xs text-ink-muted">{tn("filters.noLocation", unknownLocationCount)}</p>
      )}
      <p className="rule pt-3 text-xs text-ink-muted">{t("filters.onlineNeverPinned")}</p>
    </div>
  );
}
