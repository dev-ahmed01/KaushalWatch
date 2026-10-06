import Link from 'next/link';
import { ArrowRight, Camera, FileSearch, Phone, Sparkles } from 'lucide-react';
import { buttonVariants } from '../components/ui/button';

const actions = [
  { priority: 'High', centre: 'Bengaluru TC-04', title: 'Review attendance evidence', reason: 'Attendance gap persisted across 3 periods.', icon: FileSearch, href: '/centres/DEMO-KA-104/evidence' },
  { priority: 'Medium', centre: 'Hubballi TC-03', title: 'Contact centre head', reason: 'Infrastructure discrepancy has repeated.', icon: Phone, href: '/centres/DEMO-KA-303' },
  { priority: 'Medium', centre: 'Tumakuru TC-07', title: 'Request virtual verification', reason: 'Camera trust is insufficient.', icon: Camera, href: '/centres/DEMO-KA-207/evidence' },
  { priority: 'Low', centre: 'Belagavi TC-09', title: 'Keep under observation', reason: 'No new discrepancy requires action.', icon: Sparkles, href: '/centres/DEMO-KA-509' },
];

export default function ActionsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-[34px] font-medium tracking-[-0.035em] text-[#152238]">Actions</h1>
        <p className="mt-1 text-[15px] text-[#667085]">AI-recommended next steps for officers.</p>
      </div>

      <section className="rounded-[18px] border border-[#E3EAF3] bg-white p-7 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
        <div className="flex items-center gap-2 text-[13px] font-medium text-[#155EEF]"><Sparkles size={15} /> From KaushalAI</div>
        <h2 className="mt-2 text-[27px] font-medium tracking-[-0.025em] text-[#152238]">Today’s recommended actions</h2>
        <p className="mt-2 max-w-2xl text-[14px] leading-6 text-[#667085]">Start with the attendance discrepancy in Bengaluru. Follow with Hubballi infrastructure context and Tumakuru camera verification.</p>
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_300px]">
        <section className="rounded-[18px] border border-[#E3EAF3] bg-white px-6 py-5 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <h2 className="text-[18px] font-medium text-[#152238]">Action queue</h2>
          <div className="mt-2 divide-y divide-[#EEF2F6]">
            {actions.map((item,index) => {
              const Icon=item.icon;
              return (
                <div key={item.title} className="grid gap-4 py-4 md:grid-cols-[36px_1fr_auto] md:items-center">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#F5F8FD] text-[13px] font-medium text-[#456A9B]">{index+1}</span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2"><Icon size={15} className="text-[#155EEF]" /><span className="text-[14px] font-medium text-[#152238]">{item.title}</span></div>
                    <div className="mt-1 text-[12px] text-[#98A2B3]">{item.centre} · {item.priority}</div>
                    <div className="mt-1 text-[13px] text-[#667085]">{item.reason}</div>
                  </div>
                  <Link href={item.href} className={buttonVariants({variant:index===0?'primary':'secondary',size:'sm'})}>Open <ArrowRight size={14}/></Link>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-[18px] border border-[#E3EAF3] bg-white p-5">
            <h2 className="text-[16px] font-medium text-[#152238]">Priority mix</h2>
            <div className="mt-5 space-y-3 text-[13px] text-[#667085]">
              <div className="flex justify-between"><span>High</span><b className="font-medium text-[#152238]">1</b></div>
              <div className="flex justify-between"><span>Medium</span><b className="font-medium text-[#152238]">2</b></div>
              <div className="flex justify-between"><span>Low</span><b className="font-medium text-[#152238]">1</b></div>
            </div>
          </section>
          <section className="rounded-[18px] border border-[#E3EAF3] bg-white p-5">
            <h2 className="text-[16px] font-medium text-[#152238]">Upcoming follow-ups</h2>
            <div className="mt-3 space-y-3 text-[12px] text-[#667085]"><p>Bengaluru · attendance review</p><p>Hubballi · centre explanation</p><p>Tumakuru · virtual verification</p></div>
          </section>
        </aside>
      </div>
    </div>
  );
}
