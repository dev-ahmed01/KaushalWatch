import { redirect } from 'next/navigation';
export default async function OutcomeRedirect({ params }: { params: Promise<{ centreId: string }> }) { const { centreId } = await params; redirect(`/centres/${encodeURIComponent(centreId)}`); }
