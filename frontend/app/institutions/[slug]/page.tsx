import { InstitutionDetail } from "@/components/results/InstitutionDetail";
import { PageSurface } from "@/components/layout/PageSurface";
import { SiteFooter } from "@/components/layout/SiteFooter";

export default async function InstitutionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <>
      <PageSurface tone="chalk" />
      <InstitutionDetail slug={slug} />
      <SiteFooter tone="chalk" />
    </>
  );
}
