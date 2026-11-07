"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { character } from "@/lib/character";
import { BCP47, useT } from "@/lib/i18n";

type SRInstance = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function getSR(): (new () => SRInstance) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => SRInstance; webkitSpeechRecognition?: new () => SRInstance };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const MicIcon = ({ off = false }: { off?: boolean }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" />{off && <path d="M3 3l18 18" />}
  </svg>
);

/** Push-to-talk microphone. Never starts by itself; the transcript goes into the editable text field. The character listens along. Recognises en-CA or fr-CA to match the UI language. */
export function PushToTalk({ onTranscript, onInterim, disabled, size = "lg" }: { onTranscript: (t: string) => void; onInterim?: (t: string) => void; disabled?: boolean; size?: "lg" | "md" }) {
  const { t, locale } = useT();
  // null during SSR/hydration, then true/false once the browser is known
  const supported = useSyncExternalStore(() => () => {}, () => getSR() !== null, () => null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SRInstance | null>(null);
  const finalRef = useRef("");

  const stop = useCallback(() => {
    recRef.current?.stop();
    setListening(false);
    character.set("idle");
  }, []);

  const start = useCallback(() => {
    const SR = getSR();
    if (!SR || disabled) return;
    setError(null);
    finalRef.current = "";
    const rec = new SR();
    rec.lang = BCP47[locale];
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const tr = res[0]?.transcript ?? "";
        if (res.isFinal) finalRef.current += tr + " ";
        else interim += tr;
      }
      onInterim?.((finalRef.current + interim).trim());
    };
    rec.onerror = (e) => {
      setError(e.error === "not-allowed" ? t("ptt.denied") : t("ptt.error", { error: e.error }));
      setListening(false);
      character.set("abstain", undefined, 2500);
    };
    rec.onend = () => {
      setListening(false);
      character.set("idle");
      if (finalRef.current.trim()) onTranscript(finalRef.current.trim());
    };
    recRef.current = rec;
    rec.start();
    setListening(true);
    character.set("listening");
  }, [disabled, onInterim, onTranscript, locale, t]);

  useEffect(() => () => recRef.current?.abort(), []);

  const dim = size === "lg" ? "btn-icon btn-lg" : "btn-icon";
  if (supported === false) {
    return (
      <span className={`btn btn-secondary ${dim} cursor-not-allowed opacity-60`} title={t("ptt.unavailableTitle")} aria-label={t("ptt.unavailableAria")}><MicIcon off /></span>
    );
  }
  return (
    <span className="relative inline-flex flex-col items-center">
      <button
        type="button"
        className={`btn ${listening ? "" : "btn-secondary"} ${dim} ${listening ? "animate-pulse" : ""}`}
        aria-pressed={listening}
        aria-label={listening ? t("ptt.stopAria") : t("ptt.startAria")}
        disabled={disabled || supported === null}
        onMouseDown={() => !listening && start()}
        onMouseUp={() => listening && stop()}
        onTouchStart={(e) => { e.preventDefault(); if (!listening) start(); }}
        onTouchEnd={(e) => { e.preventDefault(); if (listening) stop(); }}
        onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !listening) { e.preventDefault(); start(); } }}
        onKeyUp={(e) => { if ((e.key === " " || e.key === "Enter") && listening) { e.preventDefault(); stop(); } }}
      >
        <MicIcon />
      </button>
      <span className="pointer-events-none absolute -bottom-5 whitespace-nowrap text-[11px] font-medium text-ink-muted" aria-live="polite">{listening ? t("ptt.listening") : t("ptt.hold")}</span>
      {error && <span role="alert" className="absolute left-0 top-full mt-6 w-[12rem] text-[11px] text-danger">{error}</span>}
    </span>
  );
}
