import { ProfileForm } from "@/components/partner/ProfileForm";
export default async function Page({ params }: { params: Promise<{ institutionId: string }> }) { const { institutionId } = await params; return <ProfileForm institutionId={institutionId} />; }
