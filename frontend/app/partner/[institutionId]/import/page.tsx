import { Suspense } from "react";
import { ImportView } from "@/components/partner/ImportView";
export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) { const { institutionId } = await params; return <Suspense fallback={null}><ImportView institutionId={institutionId} /></Suspense>; }
