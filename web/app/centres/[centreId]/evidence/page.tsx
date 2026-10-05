'use client';

import { Bot, Play, ShieldCheck } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import AnalysisModal from '../../../components/AnalysisModal';
import CentreTabs from '../../../components/CentreTabs';
import { EvidenceFrame, PageTitle, StatusPill, TechnicalDetails } from '../../../components/CalmUi';
import { Button } from '../../../components/ui/button';
import { API, getCases, getCentre } from '../../../lib/api';
import { FALLBACK_CENTRES, pillarState } from '../../../lib/presentation';
import type { CaseRecord, Centre } from '../../../lib/types';

export default function EvidencePage() {
  const { centreId } = useParams<{ centreId: string }>();
  const id = String(centreId);
  const [centre, setCentre] = useState<Centre | null>(null);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [selected, setSelected] = useState(0);

  async function load() {
    try {
      const [c, allCases] = await Promise.all([getCentre(id), getCases().catch(() => [])]);
      setCentre(c);
      setCases(allCases.filter(item => item.centre_id === id));
    } catch {
      setCentre(FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK_CENTRES[0]);
    }
  }
  useEffect(() => { void load(); }, [id]);

  const current = centre || FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK_CENTRES[0];
  const evidence = useMemo(() => cases.flatMap(item => item.evidence || []), [cases]);
  const chosen = evidence[selected] || evidence[0];
  const duplicateCount = evidence.filter(item => item.duplicate_of).length;
  const integrity = duplicateCount ? 'review' : evidence.length ? pillarState(current.evidence_integrity_status || 'clear', true) : 'unavailable';
  const src = chosen?.evidence_id ? `${API}/evidence/${chosen.evidence_id}.jpg` : undefined;

  return (
    <div>
      <PageTitle title="Evidence" description="Integrity and provenance for retained visual evidence." action={<><Button variant="ghost" onClick={() => window.dispatchEvent(new Event('kaushalwatch:assistant'))}><Bot size={17} /> Ask assistant</Button><Button variant="primary" onClick={() => setAnalysisOpen(true)}><Play size={17} /> Run analysis now</Button></>} />
      <CentreTabs centreId={id} />

      <section className="grid gap-8 lg:grid-cols-[1.25fr_.75fr]">
        <div>
          <EvidenceFrame src={src} timestamp={chosen?.created_at ? new Date(chosen.created_at).toLocaleString() : undefined} trusted={!['attention','blocked'].includes(String(current.camera_status).toLowerCase())} />
          {evidence.length > 1 && <div className="mt-4 flex flex-wrap gap-2">{evidence.slice(0, 6).map((item, index) => <button key={item.evidence_id} type="button" onClick={() => setSelected(index)} className={`kw-focus rounded-xl border px-3 py-2 text-[12px] ${index === selected ? 'border-[#93B4F6] bg-[#EFF6FF] text-[#1D4ED8]' : 'border-[#E6EAF0] bg-white text-[#667085]'}`}>Evidence {index + 1}</button>)}</div>}
        </div>

        <div className="kw-surface divide-y divide-[#EEF1F4] px-6">
          <div className="py-6"><div className="text-[13px] font-medium text-[#667085]">Evidence Integrity</div><div className="mt-3 flex flex-wrap items-center gap-2"><StatusPill state={integrity as any} />{Boolean(chosen?.metadata?.simulated) && <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[11px] text-[#667085]">Simulated evidence</span>}</div><div className="mt-2 text-[13px] text-[#667085]">{evidence.length ? 'Original evidence retained with integrity metadata.' : 'No retained evidence yet.'}</div></div>
          <div className="py-6"><div className="text-[13px] font-medium text-[#667085]">Duplicate check</div><div className="mt-2 text-[20px] font-medium text-[#172033]">{duplicateCount ? `${duplicateCount} possible duplicate${duplicateCount === 1 ? '' : 's'}` : evidence.length ? 'No duplicate signal' : 'Unavailable'}</div><div className="mt-2 text-[13px] text-[#667085]">Reviewed separately from compliance findings.</div></div>
          <div className="py-6"><div className="text-[13px] font-medium text-[#667085]">Source</div><div className="mt-2 flex items-center gap-2 text-[20px] font-medium text-[#172033]"><ShieldCheck size={18} className="text-[#667085]" /> {current.camera_id}</div><div className="mt-2 text-[13px] text-[#667085]">Position tracked, not identity.</div></div>
        </div>
      </section>

      <TechnicalDetails>
        {chosen ? <><p>Evidence ID: {chosen.evidence_id}</p><p className="break-all">SHA-256: {chosen.sha256 || 'Not available'}</p><p>Perceptual hash: {chosen.perceptual_hash || 'Not available'}</p><p>Duplicate of: {chosen.duplicate_of || 'None'}</p></> : <p>Technical integrity details appear after retained evidence is recorded.</p>}
      </TechnicalDetails>

      <AnalysisModal open={analysisOpen} onOpenChange={setAnalysisOpen} centre={current} onComplete={updated => { setCentre(updated); void load(); }} />
    </div>
  );
}
