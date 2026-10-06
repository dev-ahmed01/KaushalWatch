'use client';

import { Sparkles } from 'lucide-react';

const attendance = [
  ['Bengaluru', 88, 68],
  ['Mysuru', 76, 74],
  ['Tumakuru', 60, 48],
  ['Hubballi', 82, 78],
  ['Belagavi', 68, 66],
] as const;

export default function InsightsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-[34px] font-medium tracking-[-0.035em] text-[#152238]">Insights</h1>
        <p className="mt-1 text-[15px] text-[#667085]">Visual patterns across five PMKVY centres.</p>
      </div>

      <section className="grid gap-3 md:grid-cols-4">
        <Metric value="2" label="Verified" />
        <Metric value="2" label="Need review" />
        <Metric value="1" label="Uncertain" />
        <Metric value="0" label="Unavailable" />
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.3fr_320px]">
        <section className="rounded-[18px] border border-[#E3EAF3] bg-white p-6 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <h2 className="text-[17px] font-medium text-[#152238]">Centre health</h2>
          <div className="mt-8 flex justify-center">
            <div className="relative h-44 w-44 rounded-full" style={{ background: 'conic-gradient(#12B76A 0 40%, #F79009 40% 80%, #9BB5D8 80% 100%)' }}>
              <div className="absolute inset-7 flex flex-col items-center justify-center rounded-full bg-white">
                <span className="text-[30px] font-medium text-[#152238]">5</span>
                <span className="text-[12px] text-[#98A2B3]">centres</span>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-[18px] border border-[#E3EAF3] bg-white p-6 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <h2 className="text-[17px] font-medium text-[#152238]">Reported vs observed attendance</h2>
          <div className="mt-8 flex h-52 items-end gap-5">
            {attendance.map(([name, reported, observed]) => (
              <div key={name} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                <div className="flex h-40 items-end gap-1.5">
                  <div className="w-4 rounded-t bg-[#2563EB]" style={{ height: `${reported}%` }} />
                  <div className="w-4 rounded-t bg-[#A9C7F7]" style={{ height: `${observed}%` }} />
                </div>
                <div className="truncate text-[11px] text-[#667085]">{name}</div>
              </div>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[#E3EAF3] bg-white p-5 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <div className="flex items-center gap-2 text-[15px] font-medium text-[#155EEF]"><Sparkles size={16} /> KaushalAI insight</div>
          <div className="mt-5 space-y-5">
            <Insight number="1" title="Bengaluru attendance" body="Persistent attendance gap remains the clearest review priority." />
            <Insight number="2" title="Hubballi infrastructure" body="Repeated panel shortfall should be followed up with the centre." />
          </div>
        </aside>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartPlaceholder title="Hourly activity across centres" caption="Phase 6 will replace this with real time-bucket aggregation." />
        <ChartPlaceholder title="Infrastructure issues by centre" caption="Current visual is intentionally lightweight until live aggregation lands." />
      </div>
    </div>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return <div className="rounded-[16px] border border-[#E3EAF3] bg-white px-5 py-4"><div className="text-[26px] font-medium text-[#152238]">{value}</div><div className="text-[12px] text-[#667085]">{label}</div></div>;
}
function Insight({ number, title, body }: { number: string; title: string; body: string }) {
  return <div className="flex gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#EFF6FF] text-[12px] font-medium text-[#155EEF]">{number}</span><div><div className="text-[14px] font-medium text-[#152238]">{title}</div><p className="mt-1 text-[12px] leading-5 text-[#667085]">{body}</p></div></div>;
}
function ChartPlaceholder({ title, caption }: { title: string; caption: string }) {
  return <section className="rounded-[18px] border border-[#E3EAF3] bg-white p-6"><h2 className="text-[17px] font-medium text-[#152238]">{title}</h2><div className="mt-6 grid h-36 grid-cols-10 items-end gap-2">{[18,28,36,48,62,80,70,54,38,28].map((height,index)=><div key={index} className="rounded-t bg-[#DCE9FB]" style={{height:`${height}%`}} />)}</div><p className="mt-4 text-[12px] text-[#98A2B3]">{caption}</p></section>;
}
