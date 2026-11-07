"use client";

import { useEffect } from "react";
import { CharacterSlot } from "@/components/character/CharacterSlot";
import { character, type CharacterState } from "@/lib/character";
import { useAppSession } from "@/lib/appSession";
import { LocaleSwitch } from "@/components/layout/LocaleSwitch";

/** Flame plate at the top of every screen: eyebrow, title, Nova in the corner with a line to say, and the EN | FR switch. */
export function AppHeader({ eyebrow, title, line, mood = "idle" }: { eyebrow: string; title: string; line?: string; mood?: CharacterState }) {
  const { membership } = useAppSession();
  useEffect(() => { character.set(mood, undefined, mood === "idle" ? undefined : 2500); }, [mood]);
  return (
    <header className="app-hero halftone">
      <div className="flex items-start justify-between gap-2">
        <p className="kicker max-w-[72%] truncate">{eyebrow} <span className="accent normal-case tracking-normal">·</span> {membership.institution_name}</p>
        <LocaleSwitch className="relative z-10" />
      </div>
      <h1 className="mt-1 max-w-[70%] text-[1.9rem] leading-none">{title}</h1>
      {line && <p className="mt-2 max-w-[68%] text-sm leading-snug text-ink/85">{line}</p>}
      <div className="nova-box" aria-hidden><CharacterSlot size="mini" /></div>
    </header>
  );
}
