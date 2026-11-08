import type { Metadata } from "next";
import { Page, PageIntro } from "@/components/layout/PageIntro";
import { PageSurface } from "@/components/layout/PageSurface";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { getT } from "@/lib/i18n-server";

/** Shown on the page; bump when the practices described here change. */
const LAST_UPDATED = "2026-11-08";
/** Public contact for questions and removal requests (set NEXT_PUBLIC_PRIVACY_CONTACT on the live site). */
const CONTACT = process.env.NEXT_PUBLIC_PRIVACY_CONTACT?.trim();

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.privacy") }; }

export default async function PrivacyPage() {
  const { t, raw } = await getT();
  const sections = raw<{ h: string; p: string }[]>("privacy.sections") ?? [];
  return (
    <>
      <PageSurface tone="chalk" />
      <Page width="max-w-[900px]">
        <PageIntro eyebrow={t("privacy.eyebrow")} accent={t("privacy.accent")} title={t("privacy.title")} lede={t("privacy.lede")} />
        <div className="mt-12 space-y-9">
          {sections.map((s) => (
            <section key={s.h}>
              <h2 className="text-2xl">{s.h}</h2>
              <p className="mt-2 max-w-2xl leading-relaxed text-ink-2">{s.p}</p>
            </section>
          ))}
          <section>
            <h2 className="text-2xl">{t("privacy.contactTitle")}</h2>
            <p className="mt-2 max-w-2xl leading-relaxed text-ink-2">
              {CONTACT ? t("privacy.contact", { email: CONTACT }) : t("privacy.contactFallback")}
            </p>
            <p className="mt-4 text-sm text-ink-muted">{t("privacy.updated", { date: LAST_UPDATED })}</p>
          </section>
        </div>
      </Page>
      <SiteFooter tone="chalk" />
    </>
  );
}
