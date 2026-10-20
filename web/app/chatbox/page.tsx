import Link from 'next/link';
import { MessageCircle, ShieldCheck } from 'lucide-react';

export default function ChatboxPage() {
  return <div className="space-y-5">
    <header><h1 className="text-[28px] font-semibold text-[var(--kw-text)]">Chatbox</h1>
      <p className="text-[12px] text-[var(--kw-muted)]">One workspace for centre and officer communication</p></header>
    <section className="grid min-h-[320px] gap-0 overflow-hidden rounded-2xl border border-[var(--kw-border)] bg-white md:grid-cols-[minmax(190px,280px)_minmax(0,1fr)]">
      <aside className="border-b border-[#e7edf5] p-5 md:border-b-0 md:border-r"><h2 className="text-[13px] font-semibold">Conversations</h2>
        <p className="mt-4 text-[12px] text-[#667085]">No authorised threads available yet.</p></aside>
      <div className="flex flex-col items-center justify-center px-6 py-10 text-center"><MessageCircle size={28} className="text-[#2563eb]"/>
        <h2 className="mt-4 text-[16px] font-semibold">Messaging setup in progress</h2>
        <p className="mt-2 max-w-sm text-[12px] leading-6 text-[#667085]">Text and voice sending stay unavailable until persisted conversations and participant permissions are active. No messages are simulated as delivered.</p>
        <span className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-[#667085]"><ShieldCheck size={14}/> Private by default</span>
        <Link href="/issues" className="kw-focus mt-5 text-[12px] font-semibold text-[#2563eb]">Review issues</Link>
      </div>
    </section>
  </div>;
}
