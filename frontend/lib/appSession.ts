"use client";

import { createContext, useContext } from "react";
import type { Me, Membership } from "@/lib/types";

export const ACTIVE_INSTITUTION_KEY = "bhdh.app.institution";

export interface AppSession {
  me: Me;
  membership: Membership;
  setInstitution: (id: string) => void;
}

export const AppSessionContext = createContext<AppSession | null>(null);

/** The signed-in user and the institution they are working on (chosen in the app, remembered on the device). */
export function useAppSession(): AppSession {
  const ctx = useContext(AppSessionContext);
  if (!ctx) throw new Error("useAppSession must be used inside AppShell");
  return ctx;
}

export function readStoredInstitution(): string | null {
  try { return typeof window === "undefined" ? null : window.localStorage.getItem(ACTIVE_INSTITUTION_KEY); } catch { return null; }
}

export function storeInstitution(id: string) {
  try { window.localStorage.setItem(ACTIVE_INSTITUTION_KEY, id); } catch { /* private mode */ }
}
