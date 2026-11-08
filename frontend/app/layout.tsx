import type { Metadata, Viewport } from "next";
import { Young_Serif, Instrument_Serif, Bricolage_Grotesque } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SmoothScroll } from "@/components/motion/SmoothScroll";
import { CursorDot } from "@/components/motion/CursorDot";
import { WorldStage } from "@/components/world/WorldStage";
import { LocaleProvider } from "@/lib/i18n";
import { getLocale, getMessages, getT } from "@/lib/i18n-server";

const young = Young_Serif({ variable: "--font-young", subsets: ["latin"], weight: "400", display: "swap" });
const instrument = Instrument_Serif({ variable: "--font-instrument", subsets: ["latin"], weight: "400", style: ["normal", "italic"], display: "swap" });
const bricolage = Bricolage_Grotesque({ variable: "--font-bricolage", subsets: ["latin"], display: "swap", axes: ["opsz", "wdth"] });

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return {
    title: { default: t("meta.siteName"), template: `%s · ${t("meta.siteName")}` },
    description: t("meta.description"),
    manifest: "/manifest.webmanifest",
  };
}

export const viewport: Viewport = { themeColor: "#f2612a", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = getMessages(locale);
  const { t } = await getT();
  return (
    <html lang={locale} className={`${young.variable} ${instrument.variable} ${bricolage.variable} h-full`} data-scroll-behavior="smooth">
      <body className="grain relative min-h-full">
        <LocaleProvider locale={locale} messages={messages}>
          <a href="#main" className="skip-link">{t("common.skipToMain")}</a>
          <WorldStage />
          <SmoothScroll>
            <SiteHeader />
            <main id="main" className="relative z-10">{children}</main>
          </SmoothScroll>
          <CursorDot />
        </LocaleProvider>
      </body>
    </html>
  );
}
