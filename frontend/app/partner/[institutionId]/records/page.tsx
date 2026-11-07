import { Suspense } from "react";
import { RecordsView } from "@/components/partner/RecordsView";
export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) { const { institutionId } = await params; return <Suspense fallback={null}><RecordsView institutionId={institutionId} /></Suspense>; }
