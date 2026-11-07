import { DashboardView } from "@/components/partner/DashboardView";

export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) {
  const { institutionId } = await params;
  return <DashboardView institutionId={institutionId} />;
}
