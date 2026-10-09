'use client';

import Link from 'next/link';
import {
  ArrowLeft,
  Check,
  CircleAlert,
  FileSearch,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import {
  EvidenceFrame,
  PersistenceTimeline,
  StatusPill,
  TechnicalDetails,
} from '../../components/CalmUi';
import Toast from '../../components/Toast';
import { Button } from '../../components/ui/button';
import { API, getEvidencePack, getReviewAccess, reviewCase } from '../../lib/api';
import type { ReviewAccessStatus } from '../../lib/api';
import { caseUiState, plainCaseType } from '../../lib/presentation';
import type { EvidenceReviewPack } from '../../lib/types';

type DecisionAction = 'confirmed' | 'false_positive' | 'virtual_verification' | 'resolved';

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const id = String(caseId);
  const [pack, setPack] = useState<EvidenceReviewPack | null>(null);
  const [note, setNote] = useState('');
  const [reviewAccess, setReviewAccess] = useState<ReviewAccessStatus | null>(null);
  const [reviewAccessError, setReviewAccessError] = useState('');
  const [officerAccessKey, setOfficerAccessKey] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  async function load() {
    setError('');
    try {
      setPack(await getEvidencePack(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Case unavailable');
    }
  }

  useEffect(() => {
    void load();
  }, [id]);

  useEffect(() => {
    let active = true;
    getReviewAccess()
      .then(status => { if (active) setReviewAccess(status); })
      .catch(() => {
        if (active) setReviewAccessError('Officer review access is unavailable. Decisions are disabled.');
      });
    return () => { active = false; };
  }, []);

  const record = pack?.case;
  const evidence = record?.evidence?.[0];
  const src = evidence?.evidence_id ? API + '/evidence/' + evidence.evidence_id + '.jpg' : undefined;
  const history = pack?.review.history || [];

  async function apply(action: DecisionAction) {
    if (!record || busy) return;
    if (action !== 'virtual_verification' && !note.trim()) {
      setError('Add a short review note before a final decision.');
      return;
    }
    if (!reviewAccess) {
      setError('Officer review access is unavailable. No decision was recorded.');
      return;
    }
    if (reviewAccess.required && !officerAccessKey.trim()) {
      setError('Enter your officer access key before recording a decision.');
      return;
    }

    setBusy(action);
    setError('');
    try {
      if (record.status === 'open' && action !== 'virtual_verification') {
        await reviewCase(record.case_id, 'under_review', 'Officer opened the evidence review.', officerAccessKey.trim());
      }
      await reviewCase(
        record.case_id,
        action,
        note.trim() || 'Virtual verification requested.',
        officerAccessKey.trim(),
      );
      await load();
      setToast(
        action === 'false_positive'
          ? 'Case marked as False positive.'
          : action === 'virtual_verification'
            ? 'Virtual verification requested.'
            : action === 'resolved'
              ? 'Case resolved.'
              : 'Case confirmed for officer follow-up.',
      );
      setNote('');
      window.setTimeout(() => setToast(''), 4500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Case update failed.');
    } finally {
      setBusy('');
    }
  }

  if (!pack || !record) {
    return (
      <div>
        <Link href="/actions" className="kw-focus inline-flex items-center gap-2 rounded-lg text-[13px] font-medium text-[#667085]">
          <ArrowLeft size={15} />
          Back to actions
        </Link>
        <div className="mt-8 h-72 rounded-2xl kw-skeleton" />
        {error && <div role="alert" className="mt-4 rounded-xl bg-[#FEF3F2] px-4 py-3 text-[13px] text-[#B42318]">{error}</div>}
      </div>
    );
  }

  const simulated = Boolean(record.details?.simulated) || record.case_id.startsWith('SIM-');
  const terminal = pack.review.terminal;

  return (
    <div>
      <Link href="/actions" className="kw-focus inline-flex items-center gap-2 rounded-lg text-[13px] font-medium text-[#667085] hover:text-[#344054]">
        <ArrowLeft size={15} />
        Back to actions
      </Link>

      <header className="mb-7 mt-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[30px] font-semibold tracking-[-0.035em] text-[var(--kw-text)]">
              {plainCaseType(record.case_type)}
            </h1>
            <StatusPill state={caseUiState(record)} label={record.status.replaceAll('_', ' ').toUpperCase()} />
            {simulated && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-[11px] text-[#667085]">Simulated</span>}
          </div>
          <p className="mt-2 text-[13px] text-[#667085]">{record.centre_id} · {record.batch_id} · Case {record.case_id}</p>
        </div>
        <div className="text-right text-[11px] text-[#98A2B3]">
          <div>{pack.decision_policy}</div>
          <div className="mt-1">{pack.privacy_note}</div>
        </div>
      </header>

      <section className="grid gap-7 lg:grid-cols-[1.12fr_.88fr]">
        <div>
          <EvidenceFrame
            src={src}
            timestamp={evidence?.created_at ? new Date(evidence.created_at).toLocaleString() : undefined}
            trusted={record.camera_trust?.trusted !== false}
            emptyText={simulated ? 'Simulated case · no retained frame bundled' : 'No retained evidence preview available'}
          />

          <TechnicalDetails>
            <p>Evidence ID: {evidence?.evidence_id || 'No retained central frame'}</p>
            <p className="break-all">SHA-256: {evidence?.sha256 || 'Not available'}</p>
            <p>Perceptual hash: {evidence?.perceptual_hash || 'Not available'}</p>
            <p>Duplicate of: {evidence?.duplicate_of || 'None'}</p>
          </TechnicalDetails>
        </div>

        <div className="space-y-5">
          <section className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-5 shadow-[var(--kw-shadow)]">
            <div className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#98A2B3]">Reported vs observed</div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {pack.facts.map((fact, index) => (
                <div key={fact.label} className={index === 2 ? 'sm:col-span-2 rounded-xl bg-[#F8FAFC] p-4' : 'rounded-xl bg-[#F8FAFC] p-4'}>
                  <div className="text-[11px] font-medium text-[#667085]">{fact.label}</div>
                  <div className="mt-1.5 text-[24px] font-semibold tracking-[-0.03em] text-[var(--kw-text)]">{fact.value}</div>
                  <div className="mt-1 text-[11px] leading-5 text-[#98A2B3]">{fact.note}</div>
                </div>
              ))}
            </div>
            <div className="mt-5 border-t border-[#EEF2F6] pt-4">
              <div className="text-[12px] font-semibold text-[var(--kw-text)]">KaushalAI explanation</div>
              <p className="mt-1.5 text-[12px] leading-5 text-[#667085]">{record.summary}</p>
            </div>
          </section>

          <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
            <div className="text-[16px] font-semibold text-[var(--kw-text)]">Officer review</div>
            <p className="mt-1 text-[12px] text-[#98A2B3]">Review the evidence before recording a decision.</p>
            {reviewAccess?.mode === 'demo' && (
              <p className="mt-2 text-[11px] leading-5 text-[#667085]">Local demonstration mode · decisions are attributed to a prototype officer, not an authenticated identity.</p>
            )}
            {reviewAccessError && <div role="alert" className="mt-3 text-[12px] text-[#B42318]">{reviewAccessError}</div>}

            {!terminal ? (
              <>
                {reviewAccess?.required && (
                  <div className="mt-4">
                    <label htmlFor="officer-review-key" className="block text-[12px] font-medium text-[#475467]">Officer access key</label>
                    <input
                      id="officer-review-key"
                      type="password"
                      autoComplete="off"
                      spellCheck={false}
                      value={officerAccessKey}
                      onChange={event => setOfficerAccessKey(event.target.value)}
                      placeholder="Enter your assigned access key"
                      className="mt-2 w-full rounded-xl border border-[#D7DCE3] bg-white px-4 py-3 text-[13px] text-[#344054] outline-none focus:border-[#93B4F6]"
                    />
                    <p className="mt-1 text-[11px] text-[#667085]">Used only for officer decisions; not saved in browser storage.</p>
                  </div>
                )}
                <label htmlFor="officer-review-note" className="mt-4 block text-[12px] font-medium text-[#475467]">Decision note</label>
                <textarea
                  id="officer-review-note"
                  aria-label="Decision note"
                  value={note}
                  onChange={event => setNote(event.target.value)}
                  rows={3}
                  placeholder="Record the reason for your decision…"
                  className="mt-2 w-full resize-none rounded-xl border border-[#D7DCE3] bg-white px-4 py-3 text-[13px] leading-6 text-[#344054] outline-none focus:border-[#93B4F6]"
                />
                {error && <div role="alert" className="mt-3 rounded-xl bg-[#FEF3F2] px-4 py-3 text-[12px] text-[#B42318]">{error}</div>}
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  <Button variant="primary" disabled={Boolean(busy)} onClick={() => void apply('confirmed')}>
                    <Check size={15} />
                    Confirm discrepancy
                  </Button>
                  <Button variant="secondary" disabled={Boolean(busy)} onClick={() => void apply('false_positive')}>
                    <X size={15} />
                    False positive
                  </Button>
                  <Button variant="secondary" disabled={Boolean(busy)} onClick={() => void apply('virtual_verification')}>
                    <FileSearch size={15} />
                    Virtual verification
                  </Button>
                  <Button variant="secondary" disabled={Boolean(busy)} onClick={() => void apply('resolved')}>
                    <ShieldCheck size={15} />
                    Resolve
                  </Button>
                </div>
              </>
            ) : (
              <div className="mt-4 rounded-xl bg-[#F8FAFC] px-4 py-4 text-[12px] leading-5 text-[#667085]">
                A final officer outcome has been recorded. The evidence and audit trail remain available.
              </div>
            )}
          </section>
        </div>
      </section>

      <section className="mt-7 grid gap-7 lg:grid-cols-[1.12fr_.88fr]">
        <div>
          <PersistenceTimeline
            points={pack.temporal_proof.points}
            summary={pack.temporal_proof.summary}
          />
          {pack.temporal_proof.points.some(point => point.note) && (
            <div className="mt-3 divide-y divide-[#EEF2F6] rounded-[16px] border border-[#E6EAF0] bg-white px-5">
              {pack.temporal_proof.points.map((point, index) => (
                <div key={point.label + index} className="grid gap-1 py-3 text-[11px] sm:grid-cols-[70px_1fr]">
                  <span className="font-medium text-[#475467]">{point.label}</span>
                  <span className="text-[#667085]">{point.note || 'Recorded analysis point'}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[16px] font-semibold text-[var(--kw-text)]">Evidence integrity</h2>
              <p className="mt-1 text-[12px] text-[#98A2B3]">{pack.integrity.retained_count} retained evidence item{pack.integrity.retained_count === 1 ? '' : 's'}.</p>
            </div>
            <StatusPill state={pack.integrity.state} />
          </div>

          <div className="mt-5 space-y-3">
            <IntegrityCheck
              ok={pack.integrity.checks.sha256_retained}
              label="SHA-256 retained"
              unavailable={pack.integrity.retained_count === 0}
            />
            <IntegrityCheck
              ok={pack.integrity.checks.duplicate_review_clear}
              label={pack.integrity.possible_duplicate_count ? pack.integrity.possible_duplicate_count + ' possible duplicate' : 'No duplicate signal'}
              unavailable={pack.integrity.retained_count === 0}
            />
            <IntegrityCheck
              ok={pack.integrity.checks.camera_trust === 'trusted'}
              label={
                pack.integrity.checks.camera_trust === 'trusted'
                  ? 'Camera trusted'
                  : pack.integrity.checks.camera_trust === 'untrusted'
                    ? 'Camera trust failed'
                    : 'Camera trust not recorded'
              }
              unavailable={pack.integrity.checks.camera_trust === 'not_recorded'}
            />
          </div>

          <div className="mt-5 rounded-xl bg-[#F8FAFC] px-4 py-3 text-[11px] leading-5 text-[#667085]">
            Integrity signals are reviewed separately from the compliance finding. A duplicate signal does not by itself prove misconduct.
          </div>
        </section>
      </section>

      <details className="mt-7 rounded-[18px] border border-[var(--kw-border)] bg-white px-5 py-4 shadow-[var(--kw-shadow)]">
        <summary className="kw-focus cursor-pointer list-none text-[13px] font-semibold text-[#475467]">
          Audit trail · {history.length} event{history.length === 1 ? '' : 's'}
        </summary>
        <div className="mt-4 divide-y divide-[#EEF2F6] border-t border-[#EEF2F6] pt-1">
          {history.length ? history.map((item, index) => (
            <div key={item.timestamp + index} className="grid gap-1 py-3 text-[12px] md:grid-cols-[170px_1fr]">
              <span className="text-[#98A2B3]">{new Date(item.timestamp).toLocaleString()}</span>
              <div>
                <b className="font-medium text-[#344054]">{item.from_status.replaceAll('_', ' ')} → {item.to_status.replaceAll('_', ' ')}</b>
                <p className="mt-1 text-[11px] text-[#667085]">Recorded by: {item.actor || 'Unattributed legacy event'}</p>
                {item.note && <p className="mt-1 text-[#667085]">{item.note}</p>}
              </div>
            </div>
          )) : <p className="py-4 text-[12px] text-[#667085]">No officer action recorded yet.</p>}
        </div>
      </details>

      <Toast message={toast} onClose={() => setToast('')} />
    </div>
  );
}

function IntegrityCheck({
  ok,
  label,
  unavailable = false,
}: {
  ok: boolean;
  label: string;
  unavailable?: boolean;
}) {
  const Icon = unavailable ? CircleAlert : ok ? Check : X;
  const tone = unavailable ? 'text-[#667085]' : ok ? 'text-[#067647]' : 'text-[#B54708]';
  return (
    <div className={'flex items-center gap-2 text-[12px] ' + tone}>
      <Icon size={14} />
      <span>{label}</span>
    </div>
  );
}
