import { RecordDetail } from "@/components/results/RecordDetail";
import { PageSurface } from "@/components/layout/PageSurface";
import { SiteFooter } from "@/components/layout/SiteFooter";

export default async function RecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PageSurface tone="chalk" />
      <RecordDetail id={id} />
      <SiteFooter tone="chalk" />
    </>
  );
}
