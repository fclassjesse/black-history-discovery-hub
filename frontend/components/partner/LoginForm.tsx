"use client";

import { useState } from "react";
import { apiJson } from "@/lib/api";
import type { Me } from "@/lib/types";
import { Notice } from "@/components/ui/Notice";
import { useLocaleRouter, useT } from "@/lib/i18n";

export function LoginForm({ next }: { next?: string } = {}) {
  const { t } = useT();
  const router = useLocaleRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await apiJson<Me>("/api/partner/auth/login", "POST", { email, password });
      router.push(next ?? (me.memberships.length === 1 ? `/partner/${me.memberships[0].institution_id}` : "/partner"));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="plate-white mt-8 max-w-md space-y-4 p-6">
      {error && <Notice kind="error">{error}</Notice>}
      <div><label htmlFor="email" className="field">{t("partner.email")}</label><input id="email" className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
      <div><label htmlFor="password" className="field">{t("partner.password")}</label><input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
      <button type="submit" className="btn btn-lg" disabled={busy}>{busy ? t("partner.signingIn") : t("partner.signIn")}</button>
      <p className="text-xs text-ink-muted">{t("partner.demoNote")}</p>
    </form>
  );
}
