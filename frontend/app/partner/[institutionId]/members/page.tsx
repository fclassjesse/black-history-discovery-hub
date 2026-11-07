import { MembersView } from "@/components/partner/MembersView";
export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) { const { institutionId } = await params; return <MembersView institutionId={institutionId} />; }
