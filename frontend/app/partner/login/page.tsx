import type { Metadata } from "next";
import { LoginForm } from "@/components/partner/LoginForm";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { PageSurface } from "@/components/layout/PageSurface";
import { Stamp } from "@/components/art/Stamps";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.partnerLogin") }; }

export default async function LoginPage() {
  const { t } = await getT();
  return (
    <>
      <PageSurface tone="chalk" />
      <Page width="max-w-[1100px]">
        <div className="grid gap-10 lg:grid-cols-[1fr_380px] lg:items-start">
          <div>
            <PageIntro eyebrow={t("partner.loginEyebrow")} accent={t("partner.loginAccent")} title={t("partner.loginTitle")} lede={t("partner.loginLede")} />
            <LoginForm />
          </div>
          <div className="plate-ochre halftone hidden aspect-[4/5] place-items-center p-10 lg:grid" aria-hidden><Stamp kind="archive" className="w-[80%]" /></div>
        </div>
      </Page>
    </>
  );
}
