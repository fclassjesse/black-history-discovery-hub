"use client";

import { useInstitutions } from "@/lib/useInstitutions";
import { useReveal } from "@/lib/motion";
import { InstitutionTile } from "@/components/results/InstitutionTile";
import { useT } from "@/lib/i18n";

/** Poster grid of every institution in the directory. */
export function InstitutionGrid() {
  const { t } = useT();
  const { items, error } = useInstitutions();
  const ref = useReveal<HTMLUListElement>({ variant: "scale", stagger: 0.05 });
  if (error) return <p className="mt-6 text-sm text-danger" role="alert">{t("institutions.couldNotLoad", { error })}</p>;
  if (!items) return <p className="mt-6 text-sm text-ink-muted">{t("institutions.loading")}</p>;
  return (
    <ul ref={ref} className="mt-10 grid grid-cols-[repeat(auto-fill,minmax(min(100%,260px),1fr))] gap-4">
      {items.map((i, idx) => <li key={i.id} className="flex"><InstitutionTile inst={i} index={idx} className="!w-full" /></li>)}
    </ul>
  );
}

/** Backwards-compatible name. */
export const InstitutionStrip = InstitutionGrid;
