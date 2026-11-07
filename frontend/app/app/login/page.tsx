import type { Metadata } from "next";
import { LoginForm } from "@/components/partner/LoginForm";
import { Stamp } from "@/components/art/Stamps";
import { LocaleSwitch } from "@/components/layout/LocaleSwitch";
import { localePath } from "@/lib/i18n-core";
import { getLocale, getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> { const { t } = await getT(); return { title: t("meta.appLogin") }; }

export default async function AppLoginPage() {
  const { t } = await getT();
  const locale = await getLocale();
  return (
    <main className="app-main px-5 pb-10 pt-6">
      <div className="flex items-center justify-between">
        <a href={localePath(locale, "/")} className="logo-mark" aria-label={t("header.home")}><span className="bracket">[</span><span>BH</span><span className="bracket">]</span></a>
        <LocaleSwitch />
      </div>
      <div className="plate-ochre halftone mt-5 flex items-center gap-4 p-5">
        <Stamp kind="archive" className="w-20 shrink-0" />
        <div>
          <p className="kicker">{t("app.login.eyebrow")}</p>
          <h1 className="mt-1 text-[2rem] leading-none">{t("app.login.title")}</h1>
        </div>
      </div>
      <LoginForm next="/app" />
      <p className="mt-4 text-xs text-ink-muted">{t("app.login.sameAccounts")}</p>
    </main>
  );
}
