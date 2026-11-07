import { Suspense } from "react";
import type { Metadata } from "next";
import { AppHome } from "@/components/app/AppHome";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.appHome") }; }

export default async function Page() {
  const { t } = await getT();
  return <Suspense fallback={<p className="p-6 text-sm text-ink-muted">{t("common.loading")}</p>}><AppHome /></Suspense>;
}
