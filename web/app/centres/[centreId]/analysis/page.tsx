import { redirect } from 'next/navigation';
export default async function AnalysisRedirect({ params }: { params: Promise<{ centreId: string }> }) { const { centreId } = await params; redirect(`/centres/${encodeURIComponent(centreId)}`); }
