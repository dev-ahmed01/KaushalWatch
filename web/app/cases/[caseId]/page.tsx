'use client';

import Link from 'next/link';
import { ArrowLeft, CircleCheck, FileSearch, ShieldCheck } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { EvidenceFrame, PageTitle, StatusPill, TechnicalDetails } from '../../components/CalmUi';
import Toast from '../../components/Toast';
import { Button } from '../../components/ui/button';
import { API, getEvidencePack, reviewCase } from '../../lib/api';
import { DEMO_CASES } from '../../lib/demoCases';
import { caseUiState, plainCaseType } from '../../lib/presentation';
import type { CaseRecord } from '../../lib/types';

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const id = String(caseId);
  const [record, setRecord] = useState<CaseRecord | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  useEffect(() => {
    getEvidencePack(id)
      .then(payload => setRecord(payload.case))
      .catch(err => {
        const fallback = DEMO_CASES.find(item => item.case_id === id) || null;
        if (fallback) {
          setRecord(fallback);
          setError('');
          return;
        }
        setError(err instanceof Error ? err.message : 'Case unavailable');
      });
  }, [id]);

  const evidence = record?.evidence?.[0];
  const src = evidence?.evidence_id ? `${API}/evidence/${evidence.evidence_id}.jpg` : undefined;
  const terminal = ['confirmed', 'false_positive', 'resolved'].includes(record?.status || '');
  const history = useMemo(() => [...(record?.review_history || [])].reverse(), [record]);

  async function apply(action: 'confirmed' | 'false_positive' | 'virtual_verification' | 'resolved') {
    if (!record || busy) return;
    if (action !== 'virtual_verification' && !note.trim()) { setError('Add a short review note before a final decision.'); return; }
    setBusy(action); setError('');
    try {
      if (record.case_id.startsWith('SIM-')) {
        const now = new Date().toISOString();
        const prior = record.review_history || [];
        const directVirtual = action === 'virtual_verification';
        const audit = record.status === 'open' && !directVirtual
          ? [
              ...prior,
              { timestamp: now, from_status: 'open', to_status: 'under_review', note: 'Officer opened the evidence review.', actor: 'prototype_officer' },
              { timestamp: now, from_status: 'under_review', to_status: action, note: note || 'Simulated officer action', actor: 'prototype_officer' },
            ]
          : [...prior, { timestamp: now, from_status: record.status, to_status: action, note: note || 'Simulated officer action', actor: 'prototype_officer' }];
        const next: CaseRecord = { ...record, status: action, review_history: audit };
        setRecord(next);
      } else {
        let current = record;
        if (current.status === 'open' && action !== 'virtual_verification') current = await reviewCase(current.case_id, 'under_review', 'Officer opened the evidence review.');
        current = await reviewCase(current.case_id, action, note.trim() || 'Virtual verification requested.');
        setRecord(current);
      }
      setToast(action === 'false_positive' ? 'Case marked as False positive.' : action === 'virtual_verification' ? 'Virtual verification requested.' : action === 'resolved' ? 'Case resolved.' : 'Case confirmed for officer follow-up.');
      setNote('');
      window.setTimeout(() => setToast(''), 4500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Case update failed.');
    } finally { setBusy(''); }
  }

  if (!record) return <div><PageTitle title="Case" description={error || 'Loading evidence-backed case…'} /><div className="h-56 rounded-2xl kw-skeleton" /></div>;

  const simulated = record.case_id.startsWith('SIM-');
  const summary = simulated
    ? record.case_type === 'attendance_discrepancy'
      ? 'Reported attendance and sustained visual presence did not align across simulated analysis periods. This demo case is routed to an officer for a decision; no automatic compliance outcome is issued.'
      : 'Required infrastructure and simulated observed quantities did not align across review periods. This demo case is routed to an officer for a decision; no automatic compliance outcome is issued.'
    : record.case_type === 'attendance_discrepancy'
      ? 'Reported attendance and sustained visual presence did not align. The discrepancy persisted across trusted evidence periods, so KaushalWatch created a case for officer review rather than issuing an automatic compliance decision.'
      : record.case_type === 'infrastructure_compliance'
        ? 'Required infrastructure and sustained camera-verifiable evidence did not align. Retained evidence is available for an officer to determine the appropriate outcome.'
        : 'Recorded evidence produced a persistent discrepancy. KaushalWatch retained the evidence and routed it to an officer rather than deciding the outcome automatically.';

  return (
    <div>
      <div className="mb-7"><Link href="/cases" className="kw-focus inline-flex items-center gap-2 rounded-lg text-[13px] font-medium text-[#667085] hover:text-[#344054]"><ArrowLeft size={15} /> Back to cases</Link></div>
      <PageTitle title={plainCaseType(record.case_type)} description={`Case ${record.case_id}`} />

      <div className="mb-10 flex flex-wrap items-center gap-3"><StatusPill state={caseUiState(record)} label={record.status.replaceAll('_', ' ').toUpperCase()} />{record.case_id.startsWith('SIM-') && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-xs text-[#667085]">Simulated</span>}<span className="text-[13px] text-[#667085]">{record.centre_id} · {record.batch_id}</span></div>

      <section className="grid gap-10 lg:grid-cols-[1.15fr_.85fr]">
        <div>
          <EvidenceFrame
            src={src}
            timestamp={evidence?.created_at ? new Date(evidence.created_at).toLocaleString() : undefined}
            trusted={(record as any).camera_trust?.trusted !== false}
            emptyText={simulated ? 'Simulated case · no retained frame bundled' : 'No retained evidence preview available'}
          />
          <TechnicalDetails>
            <p>Evidence ID: {evidence?.evidence_id || 'No retained central frame'}</p>
            <p className="break-all">SHA-256: {evidence?.sha256 || 'Not available'}</p>
            <p>Duplicate signal: {evidence?.duplicate_of ? `Possible duplicate of ${evidence.duplicate_of}` : 'None recorded'}</p>
          </TechnicalDetails>
        </div>

        <div>
          <div className="text-[13px] font-medium text-[#667085]">Plain-language summary</div>
          <p className="mt-3 text-[16px] leading-7 text-[#344054]">{summary}</p>

          {!terminal ? <div className="mt-9 border-t border-[#E6EAF0] pt-7">
            <label className="block text-[13px] font-medium text-[#667085]">Officer note</label>
            <textarea value={note} onChange={event => setNote(event.target.value)} rows={3} placeholder="Record the reason for your decision…" className="mt-2 w-full resize-none rounded-xl border border-[#D7DCE3] bg-white px-4 py-3 text-[14px] leading-6 text-[#344054] outline-none focus:border-[#93B4F6]" />
            {error && <div className="mt-3 rounded-xl bg-[#FEF3F2] px-4 py-3 text-[13px] text-[#B42318]">{error}</div>}
            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              <Button variant="primary" disabled={Boolean(busy)} onClick={() => void apply('confirmed')}><CircleCheck size={16} /> Confirm</Button>
              <Button variant="secondary" disabled={Boolean(busy)} onClick={() => void apply('false_positive')}>False positive</Button>
              <Button variant="secondary" disabled={Boolean(busy)} onClick={() => void apply('virtual_verification')}><FileSearch size={16} /> Virtual verification</Button>
              <Button variant="secondary" disabled={Boolean(busy)} onClick={() => void apply('resolved')}><ShieldCheck size={16} /> Resolve</Button>
            </div>
            <p className="mt-3 text-xs text-[#98A2B3]">AI surfaces evidence. Officers decide.</p>
          </div> : <div className="mt-9 rounded-2xl bg-[#F8FAFC] p-5 text-[14px] text-[#667085]">This case has a final officer outcome. The audit trail remains available below.</div>}
        </div>
      </section>

      <details className="mt-14 rounded-2xl border border-[#E6EAF0] bg-white px-6 py-5">
        <summary className="kw-focus cursor-pointer list-none text-[14px] font-medium text-[#344054]">Audit trail · {history.length} event{history.length === 1 ? '' : 's'}</summary>
        <div className="mt-5 space-y-4 border-t border-[#EEF1F4] pt-5">
          {history.length ? history.map((item, index) => <div key={`${item.timestamp}-${index}`} className="grid gap-1 text-[13px] md:grid-cols-[180px_1fr]"><span className="text-[#98A2B3]">{new Date(item.timestamp).toLocaleString()}</span><div><b className="font-medium text-[#344054]">{item.from_status.replaceAll('_', ' ')} → {item.to_status.replaceAll('_', ' ')}</b>{item.note && <p className="mt-1 text-[#667085]">{item.note}</p>}</div></div>) : <p className="text-[13px] text-[#667085]">No officer action recorded yet.</p>}
        </div>
      </details>
      <Toast message={toast} onClose={() => setToast('')} />
    </div>
  );
}
