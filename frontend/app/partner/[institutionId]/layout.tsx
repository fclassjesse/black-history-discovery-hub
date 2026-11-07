import { PartnerShell } from "@/components/partner/PartnerShell";

export default async function PartnerLayout({ children, params }: { children: React.ReactNode; params: Promise<{ institutionId: string }> }) {
  const { institutionId } = await params;
  return <PartnerShell institutionId={institutionId}>{children}</PartnerShell>;
}
