import { ShelfScanView } from "@/components/partner/ShelfScanView";
export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) { const { institutionId } = await params; return <ShelfScanView institutionId={institutionId} />; }
