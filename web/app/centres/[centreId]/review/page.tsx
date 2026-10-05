import { redirect } from 'next/navigation';
export default async function ReviewRedirect({ params }: { params: Promise<{ centreId: string }> }) { const { centreId } = await params; redirect(`/cases?centre=${encodeURIComponent(centreId)}`); }
