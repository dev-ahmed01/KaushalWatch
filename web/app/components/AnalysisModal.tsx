'use client';

import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, CircleHelp, FileVideo2, LoaderCircle, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { API, getCentre, getDashboard, getRuntimeReadiness, officerFetch } from '../lib/api';
import type { Centre } from '../lib/types';
import { Button } from './ui/button';

const STEP_LABELS = ['Manifest reading', 'Visual evidence', 'Temporal Proof', 'Case evidence'] as const;
type StepState = 'pending' | 'running' | 'done' | 'error';

type Step = { label: (typeof STEP_LABELS)[number]; state: StepState; detail: string };

function initialSteps(): Step[] {
  return [
    { label: 'Manifest reading', state: 'pending', detail: 'Required job-role checks and analysis availability.' },
    { label: 'Visual evidence', state: 'pending', detail: 'Attendance, practical activity and infrastructure evidence.' },
    { label: 'Temporal Proof', state: 'pending', detail: 'Persistence is evaluated across time, not one frame.' },
    { label: 'Case evidence', state: 'pending', detail: 'Evidence-backed discrepancies are prepared for officer review.' },
  ];
}

export default function AnalysisModal({ open, onOpenChange, centre, onComplete }: { open: boolean; onOpenChange: (open: boolean) => void; centre: Centre; onComplete?: (centre: Centre) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [reported, setReported] = useState(Math.min(centre.trainees || 28, 28));
  const [steps, setSteps] = useState<Step[]>(initialSteps);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [technical, setTechnical] = useState<string[]>([]);

  const current = useMemo(() => steps.findIndex(step => step.state === 'running'), [steps]);

  function update(index: number, state: StepState, detail?: string) {
    setSteps(items => items.map((item, i) => i === index ? { ...item, state, ...(detail ? { detail } : {}) } : item));
  }

  async function post(path: string, body: FormData) {
    const response = await officerFetch(`${API}${path}`, { method: 'POST', body });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || 'Analysis step failed');
    return payload;
  }

  async function run() {
    if (!file || running) return;
    setRunning(true);
    setError('');
    setTechnical([]);
    setSteps(initialSteps());
    try {
      update(0, 'running');
      const [fresh, readiness] = await Promise.all([getCentre(centre.centre_id), getRuntimeReadiness()]);
      setTechnical([
        `Vision profile: ${readiness?.vision_profile?.profile_id || 'unavailable'} · ${readiness?.runtime_alignment?.aligned ? 'aligned' : 'drifted / unavailable'}`,
        `Attendance runtime: ${readiness?.attendance?.ready ? 'ready' : 'unavailable'}`,
        `Practical runtime: ${readiness?.practical_work?.ready ? 'ready' : 'unavailable'}`,
        `Infrastructure runtime: ${readiness?.infrastructure?.ready ? 'ready' : 'unavailable'}`,
      ]);
      update(0, 'done', `${fresh.job_role} · ${fresh.batch_id}`);

      update(1, 'running');
      const attendanceBody = new FormData();
      attendanceBody.append('file', file);
      attendanceBody.append('reported_attendance', String(reported));
      attendanceBody.append('centre_id', centre.centre_id);
      attendanceBody.append('batch_id', centre.batch_id);
      attendanceBody.append('camera_id', centre.camera_id);
      const attendance = await post('/api/process-video', attendanceBody);

      const practicalBody = new FormData();
      practicalBody.append('file', file);
      practicalBody.append('authorization', 'valid');
      practicalBody.append('zone_profile', 'authorized');
      practicalBody.append('centre_id', centre.centre_id);
      practicalBody.append('batch_id', centre.batch_id);
      practicalBody.append('camera_id', centre.camera_id);
      const practical = await post('/api/process-practical-activity', practicalBody).catch(err => ({ _error: err instanceof Error ? err.message : 'Practical analysis unavailable' }));

      const infrastructureBody = new FormData();
      infrastructureBody.append('file', file);
      infrastructureBody.append('centre_id', centre.centre_id);
      infrastructureBody.append('batch_id', centre.batch_id);
      infrastructureBody.append('camera_id', centre.camera_id);
      infrastructureBody.append('demo_profile', 'discrepancy');
      const infrastructure = await post('/api/process-infrastructure-video', infrastructureBody).catch(err => ({ _error: err instanceof Error ? err.message : 'Infrastructure analysis unavailable' }));
      const unavailable = [practical, infrastructure].filter((item: any) => item?._error).length;
      update(1, unavailable ? 'error' : 'done', unavailable ? `${unavailable} checkpoint${unavailable === 1 ? '' : 's'} unavailable; conclusions remain suspended there.` : 'Trusted visual evidence processed.');

      update(2, 'running');
      const temporalDetail = attendance?.decision === 'attendance_exception'
        ? 'Attendance discrepancy persisted across multiple trusted periods.'
        : attendance?.decision === 'compliant'
          ? 'No persistent attendance discrepancy was recorded.'
          : 'Temporal conclusion unavailable where camera or detector trust was insufficient.';
      update(2, 'done', temporalDetail);

      update(3, 'running');
      const dashboard = await getDashboard(centre.centre_id);
      const updated = await getCentre(centre.centre_id);
      const count = Number(dashboard?.open_cases ?? dashboard?.pending_cases?.length ?? updated.pending_cases ?? 0);
      update(3, 'done', count ? `${count} case${count === 1 ? '' : 's'} ready for officer review.` : 'No new officer decision is required.');
      onComplete?.(updated);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Analysis could not be completed.';
      setError(message);
      setSteps(items => items.map(item => item.state === 'running' ? { ...item, state: 'error', detail: message } : item));
    } finally {
      setRunning(false);
    }
  }

  function close(next: boolean) {
    if (!running) onOpenChange(next);
  }

  return (
    <Dialog.Root open={open} onOpenChange={close}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild><motion.div className="fixed inset-0 z-40 bg-[#172033]/15" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} /></Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div className="kw-scrollbar fixed left-1/2 top-1/2 z-50 max-h-[calc(100vh-24px)] w-[min(680px,calc(100vw-24px))] overflow-y-auto rounded-2xl border border-[#E6EAF0] bg-white p-5 shadow-[0_12px_32px_rgba(16,24,40,.12)] sm:p-7" initial={{ opacity: 0, x: '-50%', y: '-48%' }} animate={{ opacity: 1, x: '-50%', y: '-50%' }} exit={{ opacity: 0, x: '-50%', y: '-48%' }} transition={{ duration: 0.18 }}>
                <div className="flex items-start justify-between">
                  <div>
                    <Dialog.Title className="text-xl font-medium text-[#172033]">Run analysis</Dialog.Title>
                    <Dialog.Description className="mt-1 text-[14px] text-[#667085]">One recording, four auditable steps.</Dialog.Description>
                  </div>
                  <Dialog.Close asChild><Button variant="ghost" size="icon" disabled={running} aria-label="Close analysis"><X size={18} /></Button></Dialog.Close>
                </div>

                <div className="mt-7 grid gap-4 md:grid-cols-[1fr_150px]">
                  <label className="rounded-2xl border border-dashed border-[#D7DCE3] bg-[#FBFCFD] p-5">
                    <div className="flex items-center gap-3"><FileVideo2 size={20} className="text-[#667085]" /><span className="text-[14px] font-medium text-[#344054]">Visual evidence</span></div>
                    <input type="file" accept="video/*" className="mt-4 block w-full text-[13px] text-[#667085] file:mr-3 file:rounded-lg file:border-0 file:bg-[#EFF6FF] file:px-3 file:py-2 file:text-[13px] file:font-medium file:text-[#1D4ED8]" onChange={event => setFile(event.target.files?.[0] || null)} disabled={running} />
                    <p className="mt-3 text-xs text-[#98A2B3]">Fixed-camera evidence only. People remain anonymized.</p>
                  </label>
                  <label className="rounded-2xl border border-[#E6EAF0] p-5 text-[13px] text-[#667085]">
                    Reported attendance <span className="ml-1 rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[11px]">Simulated</span>
                    <input type="number" min="0" value={reported} onChange={event => setReported(Number(event.target.value))} disabled={running} className="mt-3 h-11 w-full rounded-xl border border-[#D7DCE3] px-3 text-lg font-medium text-[#172033] outline-none focus:border-[#93B4F6]" />
                  </label>
                </div>

                <div className="mt-7 space-y-2" aria-live="polite" aria-busy={running}>
                  {steps.map((step, index) => (
                    <div key={step.label} className="flex items-start gap-4 rounded-xl px-2 py-3">
                      <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${step.state === 'done' ? 'bg-[#ECFDF3] text-[#067647]' : step.state === 'error' ? 'bg-[#F2F4F7] text-[#475467]' : step.state === 'running' ? 'bg-[#EFF6FF] text-[#2563EB]' : 'bg-[#F2F4F7] text-[#98A2B3]'}`}>
                        {step.state === 'done' ? <Check size={15} /> : step.state === 'error' ? <CircleHelp size={15} /> : step.state === 'running' ? <LoaderCircle size={15} className="animate-spin" /> : <span className="text-xs font-medium">{index + 1}</span>}
                      </span>
                      <div className="min-w-0"><div className="text-[14px] font-medium text-[#172033]">{step.label}</div><div className="mt-0.5 text-[13px] leading-5 text-[#667085]">{step.detail}</div></div>
                    </div>
                  ))}
                </div>

                {error && <div role="alert" className="mt-4 rounded-xl bg-[#FEF3F2] px-4 py-3 text-[13px] text-[#B42318]">{error}</div>}
                {technical.length > 0 && <details className="mt-4 text-[13px] text-[#667085]"><summary className="cursor-pointer font-medium">Technical details</summary><div className="mt-2 space-y-1">{technical.map(item => <div key={item}>{item}</div>)}</div></details>}

                <div className="mt-7 flex items-center justify-between border-t border-[#EEF1F4] pt-5">
                  <p className="text-xs text-[#98A2B3]">AI surfaces evidence. Officers decide.</p>
                  <Button variant="primary" disabled={!file || running} onClick={() => void run()}>{running ? 'Analysis running' : current === -1 && steps.every(step => step.state === 'done' || step.state === 'error') ? 'Run again' : 'Start analysis'}</Button>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
