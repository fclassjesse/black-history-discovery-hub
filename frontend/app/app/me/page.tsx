import { Suspense } from "react";
import type { Metadata } from "next";
import { MeView } from "@/components/app/MeView";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.appMe") }; }

export default async function Page() {
  const { t } = await getT();
  return <Suspense fallback={<p className="p-6 text-sm text-ink-muted">{t("common.loading")}</p>}><MeView /></Suspense>;
}
