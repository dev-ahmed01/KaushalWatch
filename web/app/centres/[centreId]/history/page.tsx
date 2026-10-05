import { redirect } from 'next/navigation';
export default async function HistoryRedirect({ params }: { params: Promise<{ centreId: string }> }) { const { centreId } = await params; redirect(`/reports?centre=${encodeURIComponent(centreId)}`); }
