"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";
import { useLocaleRouter } from "@/lib/i18n";

export function useMe(redirect = true) {
  const router = useLocaleRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    apiGet<Me>("/api/partner/auth/me")
      .then(setMe)
      .catch((e: ApiError) => { if (redirect && e.status === 401) router.replace("/partner/login"); })
      .finally(() => setLoading(false));
  }, [redirect, router]);
  return { me, loading };
}

export function base(institutionId: string) {
  return `/api/partner/institutions/${institutionId}`;
}
