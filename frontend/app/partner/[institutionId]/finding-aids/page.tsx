import { FindingAidView } from "@/components/partner/FindingAidView";
export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) { const { institutionId } = await params; return <FindingAidView institutionId={institutionId} />; }
