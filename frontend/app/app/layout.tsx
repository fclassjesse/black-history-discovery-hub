import type { Metadata, Viewport } from "next";
import { AppShell } from "@/components/app/AppShell";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return { title: { default: t("meta.institutionApp"), template: "%s · BH Shelf" }, appleWebApp: { capable: true, title: "BH Shelf", statusBarStyle: "default" }, icons: { apple: "/apple-touch-icon.png", icon: "/icon-192.png" } };
}
export const viewport: Viewport = { themeColor: "#f2612a", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
