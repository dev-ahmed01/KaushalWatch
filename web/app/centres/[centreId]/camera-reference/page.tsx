'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import CentreTabs from '../../../components/CentreTabs';
import { API, SECURE_PROXY, getOfficerContext, officerFetch } from '../../../lib/api';

type Ref = {
  centre_id: string; camera_id: string; revision: number; state: string;
  reference_digest?: string; capture_id?: string; source_review_id?: string;
  proposed_by?: string; reviewed_by?: string | null; independent_review_id?: string | null;
  production_binding: false; actual_reference_verified: false;
};
type Officer = { role: string; centre_ids: string[]; can_review: boolean };

async function parse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || 'Camera reference workflow unavailable');
  return body as T;
}

export default function CameraReferencePage() {
  const { centreId } = useParams<{ centreId: string }>();
  const id = String(centreId);
  const endpoint = API + '/api/centres/' + encodeURIComponent(id) + '/camera-reference';
  const [ref, setRef] = useState<Ref | null>(null);
  const [officer, setOfficer] = useState<Officer | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [digest, setDigest] = useState('');
  const [capture, setCapture] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [reviewId, setReviewId] = useState('');
  const [checks, setChecks] = useState([false, false, false]);
  const [reason, setReason] = useState('');

  const load = useCallback(async () => {
    if (!SECURE_PROXY) throw new Error('Protected officer login is required.');
    const [permissions, reference] = await Promise.all([
      getOfficerContext(), officerFetch(endpoint).then(r => parse<Ref>(r)),
    ]);
    setOfficer(permissions);
    setRef(reference);
  }, [endpoint]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    void load().catch(err => {
      if (active) setError(err instanceof Error ? err.message : 'Reference data unavailable');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>, action: 'propose' | 'review' | 'suspend') {
    event.preventDefault();
    if (!ref) return;
    const payload = action === 'propose' ? {
      expected_revision: ref.revision,
      reference_digest: digest.trim(), capture_id: capture.trim(), source_review_id: sourceId.trim(),
    } : action === 'review' ? {
      expected_revision: ref.revision, independent_review_id: reviewId.trim(),
      verified_healthy: checks[0], verified_same_view: checks[1], compared_independently: checks[2],
    } : {
      expected_revision: ref.revision, reason: reason.trim(),
    };
    setPending(true); setMessage(''); setError('');
    try {
      const updated = await parse<Ref>(await officerFetch(endpoint + '/' + action, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      }));
      setRef(updated);
      setChecks([false, false, false]);
      setMessage(action === 'review'
        ? 'Review attestation recorded. Reference binding and camera activation remain disabled.'
        : action === 'propose' ? 'Metadata proposal saved for independent review.' : 'Reference record suspended.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review could not be saved');
    } finally {
      setPending(false);
    }
  }

  const canPropose = officer?.role === 'centre_reviewer';
  const canReview = officer?.role === 'network_admin';
  const fieldStyle = 'kw-focus mt-1 block w-full rounded-lg border border-[#D0D5DD] bg-white px-3 py-2.5 text-[13px] text-[#101828]';
  const buttonStyle = 'kw-focus rounded-lg bg-[#2563EB] px-4 py-2.5 text-[13px] font-semibold text-white disabled:opacity-50';
  return (
    <div className="space-y-6">
      <Link href={'/centres/' + encodeURIComponent(id)}
        className="kw-focus text-[12px] text-[#667085] hover:text-[#344054]">← Centre overview</Link>
      <div>
        <h1 className="text-[28px] font-semibold tracking-[-0.03em] text-[#101828]">Camera reference review</h1>
        <p className="mt-1 text-[13px] text-[#667085]">Officer-only, staging metadata workflow. No reference activation or attendance decisions.</p>
      </div>
      <CentreTabs centreId={id} />
      {loading && <p role="status" className="text-[13px] text-[#667085]">Checking officer permissions and reference status…</p>}
      {error && <p role="alert" className="rounded-xl border border-[#E7B8B2] bg-[#FFF8F7] p-4 text-[13px] text-[#B42318]">{error}</p>}
      {message && <p role="status" className="rounded-xl border border-[#C8E5D6] bg-[#F4FBF7] p-4 text-[13px] text-[#247448]">{message}</p>}
      {ref && (
        <>
          <section className="rounded-[18px] border border-[#E4EAF2] bg-white p-6">
            <h2 className="text-[17px] font-semibold text-[#101828]">Reference governance</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <div><dt className="text-[11px] text-[#667085]">Camera</dt><dd className="mt-1 text-[13px]">{ref.camera_id}</dd></div>
              <div><dt className="text-[11px] text-[#667085]">Status</dt><dd className="mt-1 text-[13px] font-semibold">{ref.state.replaceAll('_', ' ')}</dd></div>
              <div><dt className="text-[11px] text-[#667085]">Revision</dt><dd className="mt-1 text-[13px]">{ref.revision}</dd></div>
              <div><dt className="text-[11px] text-[#667085]">Independent reviewer</dt><dd className="mt-1 text-[13px]">{ref.reviewed_by || 'Not recorded'}</dd></div>
            </dl>
            <p className="mt-5 rounded-lg bg-[#F7F9FC] p-3 text-[12px] leading-5 text-[#475467]">
              A recorded review is not verification of the underlying camera image. Reference binding, compliance and attendance actions remain disabled.
            </p>
          </section>

          {canPropose && ['UNENROLLED','SUSPENDED','REVOKED'].includes(ref.state) && (
            <form onSubmit={event => void submit(event, 'propose')} className="space-y-4 rounded-[18px] border border-[#E4EAF2] bg-white p-6">
              <h2 className="text-[17px] font-semibold">Propose reference metadata</h2>
              <p className="text-[12px] text-[#667085]">The 64-character digest must come from a separately handled canonical pixel reference. No video or images are accepted here.</p>
              <label className="block text-[12px] font-medium">Canonical raw-pixel SHA-256
                <input aria-label="Canonical raw-pixel SHA-256" required minLength={64} maxLength={64} pattern="[a-f0-9]{64}" value={digest} onChange={e => setDigest(e.target.value)} className={fieldStyle} />
              </label>
              <label className="block text-[12px] font-medium">Capture record ID
                <input aria-label="Capture record ID" required maxLength={128} value={capture} onChange={e => setCapture(e.target.value)} className={fieldStyle} />
              </label>
              <label className="block text-[12px] font-medium">Source review record ID
                <input aria-label="Source review record ID" required maxLength={128} value={sourceId} onChange={e => setSourceId(e.target.value)} className={fieldStyle} />
              </label>
              <button disabled={pending} className={buttonStyle}>Submit proposal</button>
            </form>
          )}

          {canReview && ref.state === 'PENDING_REVIEW' && (
            <form onSubmit={event => void submit(event, 'review')} className="space-y-4 rounded-[18px] border border-[#E4EAF2] bg-white p-6">
              <h2 className="text-[17px] font-semibold">Independent officer review</h2>
              <div className="break-all rounded-lg bg-[#F7F9FC] p-3 text-[12px] text-[#475467]">
                <div>Digest: {ref.reference_digest}</div><div>Capture: {ref.capture_id}</div>
                <div>Source: {ref.source_review_id}</div><div>Proposed by: {ref.proposed_by}</div>
              </div>
              <label className="block text-[12px] font-medium">Independent review record ID
                <input aria-label="Independent review record ID" required maxLength={128} value={reviewId} onChange={e => setReviewId(e.target.value)} className={fieldStyle} />
              </label>
              {['Healthy camera reference inspected', 'Intended viewpoint compared', 'Independent source comparison performed'].map((label, index) =>
                <label key={label} className="flex items-start gap-3 text-[13px] text-[#475467]">
                  <input type="checkbox" className="mt-1" checked={checks[index]}
                    onChange={e => setChecks(old => old.map((v, j) => index === j ? e.target.checked : v))} />
                  {label}
                </label>)}
              <button disabled={pending || !checks.every(Boolean)} className={buttonStyle}>Record review — activation disabled</button>
            </form>
          )}

          {canReview && ['PENDING_REVIEW','REVIEWED_NOT_BOUND'].includes(ref.state) && (
            <form onSubmit={event => void submit(event, 'suspend')} className="space-y-3 rounded-[18px] border border-[#E4EAF2] bg-white p-6">
              <h2 className="text-[17px] font-semibold">Suspend reference record</h2>
              <input aria-label="Suspension reason" required maxLength={128} value={reason} onChange={e => setReason(e.target.value)}
                placeholder="Short suspension reason" className={fieldStyle} />
              <button disabled={pending} className="kw-focus rounded-lg border border-[#D0D5DD] px-4 py-2.5 text-[13px] font-medium disabled:opacity-50">Suspend record</button>
            </form>
          )}
          {!canPropose && !canReview && <p className="text-[12px] text-[#667085]">Your officer role can view this record but not change it.</p>}
        </>
      )}
      {!loading && !ref && !error && <p role="status" className="text-[13px]">Reference review unavailable.</p>}
    </div>
  );
}
