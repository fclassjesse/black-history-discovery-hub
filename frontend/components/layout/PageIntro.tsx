"use client";

import type { ReactNode } from "react";
import { useReveal, SplitWords } from "@/lib/motion";

/** Editorial page header: eyebrow with the square, slab headline, lede. Chalk pages. */
export function PageIntro({ eyebrow, accent, title, lede, children }: { eyebrow: string; accent?: string; title: string; lede?: ReactNode; children?: ReactNode }) {
  const ref = useReveal<HTMLDivElement>({ variant: "words", stagger: 0.04 });
  return (
    <div ref={ref} className="pt-6 sm:pt-10">
      <p className="eyebrow text-ink"><span className="sq" /> {eyebrow}{accent && <span className="accent">{accent}</span>}</p>
      <h1 className="mt-4 max-w-5xl text-[length:var(--text-h1)]" style={{ perspective: 800 }}><SplitWords text={title} /></h1>
      {lede && <div className="mt-5 max-w-2xl text-lg leading-snug text-ink-2">{lede}</div>}
      {children}
    </div>
  );
}

export function Page({ children, width = "max-w-[1600px]" }: { children: ReactNode; width?: string }) {
  return <div className={`mx-auto ${width} px-[var(--gutter)] pb-[var(--space-section)]`}>{children}</div>;
}
