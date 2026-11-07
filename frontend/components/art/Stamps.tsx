/**
 * Cartoon "stamps": flat, ink-outlined illustrations for institution kinds.
 * Hand-drawn feel: slightly wobbly shapes, halftone fills, thick ink lines.
 */
import type { SVGProps } from "react";

export type StampKind = "museum" | "library" | "archive" | "community" | "university" | "online_repository" | "unknown";

const INK = "var(--ink)";

function Halftone({ id }: { id: string }) {
  return (
    <pattern id={id} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">
      <circle cx="1.4" cy="1.4" r="1" fill={INK} opacity="0.35" />
    </pattern>
  );
}

const common = { strokeWidth: 3, stroke: INK, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function Stamp({ kind, className, ...rest }: { kind: StampKind | string; className?: string } & SVGProps<SVGSVGElement>) {
  const k = (["museum", "library", "archive", "community", "university", "online_repository"].includes(kind) ? kind : "unknown") as StampKind;
  const pid = `ht-${k}`;
  return (
    <svg viewBox="0 0 160 160" className={className} role="img" aria-hidden {...rest}>
      <defs><Halftone id={pid} /></defs>
      {k === "museum" && (
        <g {...common}>
          <path d="M22 62 L80 26 L138 62 Z" fill="var(--sun)" />
          <path d="M22 62 L80 26 L138 62 Z" fill={`url(#${pid})`} />
          <rect x="30" y="62" width="100" height="10" fill="var(--cream)" />
          {[42, 66, 90, 114].map((x) => <rect key={x} x={x} y="72" width="10" height="44" rx="3" fill="var(--cream)" />)}
          <rect x="24" y="116" width="112" height="14" rx="3" fill="var(--rose)" />
          <path d="M80 26 L80 10 L100 14 L80 20" fill="var(--flame)" />
          <circle cx="80" cy="50" r="6" fill={INK} stroke="none" />
        </g>
      )}
      {k === "library" && (
        <g {...common}>
          <rect x="30" y="92" width="100" height="22" rx="4" fill="var(--sun)" transform="rotate(-3 80 103)" />
          <rect x="34" y="70" width="92" height="22" rx="4" fill="var(--rose)" transform="rotate(2 80 81)" />
          <rect x="38" y="48" width="84" height="22" rx="4" fill="var(--cream)" transform="rotate(-2 80 59)" />
          <rect x="38" y="48" width="84" height="22" rx="4" fill={`url(#${pid})`} transform="rotate(-2 80 59)" />
          <path d="M50 59 h40 M46 81 h50 M44 103 h60" />
          <path d="M112 44 C 112 30, 134 30, 134 44 L134 50 L112 50 Z" fill="var(--moss)" />
          <path d="M123 50 v18" />
          <path d="M30 120 h100" />
          <path d="M40 120 v14 M120 120 v14" />
        </g>
      )}
      {k === "archive" && (
        <g {...common}>
          <rect x="28" y="48" width="104" height="80" rx="8" fill="var(--ochre)" />
          <rect x="28" y="48" width="104" height="80" rx="8" fill={`url(#${pid})`} />
          <path d="M28 76 h104 M28 102 h104" />
          <rect x="64" y="58" width="32" height="10" rx="5" fill="var(--cream)" />
          <rect x="64" y="84" width="32" height="10" rx="5" fill="var(--cream)" />
          <rect x="64" y="110" width="32" height="10" rx="5" fill="var(--cream)" />
          <path d="M40 48 L52 30 L108 30 L120 48" fill="var(--sun)" />
          <path d="M70 30 L70 20 L90 20 L90 30" fill="var(--rose)" />
        </g>
      )}
      {k === "community" && (
        <g {...common}>
          <path d="M26 128 L26 78 L80 40 L134 78 L134 128 Z" fill="var(--rose)" />
          <path d="M26 128 L26 78 L80 40 L134 78 L134 128 Z" fill={`url(#${pid})`} />
          <path d="M18 82 L80 36 L142 82" fill="none" />
          <circle cx="58" cy="94" r="10" fill="var(--cream)" />
          <circle cx="102" cy="94" r="10" fill="var(--cream)" />
          <path d="M44 128 C 44 110, 72 110, 72 128" fill="var(--sun)" />
          <path d="M88 128 C 88 110, 116 110, 116 128" fill="var(--moss)" />
          <path d="M72 70 c 4 -8 12 -8 8 0 c 4 -8 12 -8 8 0 l -8 10 z" fill="var(--flame)" />
        </g>
      )}
      {k === "university" && (
        <g {...common}>
          <rect x="56" y="30" width="48" height="98" rx="4" fill="var(--cream)" />
          <rect x="56" y="30" width="48" height="98" rx="4" fill={`url(#${pid})`} />
          <rect x="24" y="80" width="32" height="48" rx="4" fill="var(--sun)" />
          <rect x="104" y="80" width="32" height="48" rx="4" fill="var(--sun)" />
          <circle cx="80" cy="56" r="14" fill="var(--white)" />
          <path d="M80 56 L80 47 M80 56 L87 60" />
          <path d="M80 30 L80 16 L96 20 L80 26" fill="var(--moss)" />
          <rect x="72" y="100" width="16" height="28" rx="6" fill="var(--rose)" />
          <path d="M20 128 h120" />
        </g>
      )}
      {k === "online_repository" && (
        <g {...common}>
          <path d="M44 100 C 20 100, 22 66, 48 66 C 50 40, 92 36, 100 60 C 128 54, 140 94, 112 100 Z" fill="var(--cream)" />
          <path d="M44 100 C 20 100, 22 66, 48 66 C 50 40, 92 36, 100 60 C 128 54, 140 94, 112 100 Z" fill={`url(#${pid})`} />
          <rect x="58" y="86" width="44" height="32" rx="5" fill="var(--moss)" />
          <path d="M66 96 h28 M66 106 h18" stroke="var(--cream)" />
          <path d="M80 118 v10 M66 130 h28" />
          <path d="M112 112 l6 16 l4 -6 l6 4 l-6 -8 l6 -3 z" fill="var(--sun)" />
        </g>
      )}
      {k === "unknown" && (
        <g {...common}>
          <path d="M40 40 h60 l20 20 v60 h-80 z" fill="var(--chalk)" />
          <path d="M40 40 h60 l20 20 v60 h-80 z" fill={`url(#${pid})`} />
          <path d="M100 40 v20 h20" />
          <text x="80" y="98" textAnchor="middle" fontFamily="var(--font-display)" fontSize="44" fill={INK} stroke="none">?</text>
        </g>
      )}
    </svg>
  );
}

/** Decorative shapes used around the page (quarter circles, arches, blobs). */
export function Shape({ variant, className, color = "var(--chalk)" }: { variant: "quarter" | "arch" | "semi" | "blob" | "ring" | "star"; className?: string; color?: string }) {
  if (variant === "quarter") return <svg viewBox="0 0 100 100" className={className} aria-hidden><path d="M0 0 H100 A100 100 0 0 1 0 100 Z" fill={color} /></svg>;
  if (variant === "semi") return <svg viewBox="0 0 100 50" className={className} aria-hidden><path d="M0 50 A50 50 0 0 1 100 50 Z" fill={color} /></svg>;
  if (variant === "arch") return <svg viewBox="0 0 100 140" className={className} aria-hidden><path d="M0 140 V50 A50 50 0 0 1 100 50 V140 Z" fill={color} /></svg>;
  if (variant === "ring") return <svg viewBox="0 0 100 100" className={className} aria-hidden><circle cx="50" cy="50" r="38" fill="none" stroke={color} strokeWidth="14" /></svg>;
  if (variant === "star") return <svg viewBox="0 0 100 100" className={className} aria-hidden><path d="M50 2 L58 38 L96 42 L62 58 L72 96 L50 72 L28 96 L38 58 L4 42 L42 38 Z" fill={color} /></svg>;
  return <svg viewBox="0 0 200 200" className={className} aria-hidden><path d="M44 30 C 90 -10, 190 20, 180 90 C 172 150, 120 210, 60 180 C 0 150, 0 70, 44 30 Z" fill={color} /></svg>;
}
