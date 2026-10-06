'use client';

import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowUp, Bot, LoaderCircle, X } from 'lucide-react';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { askAssistant, getAssistantStatus } from '../lib/api';
import type { AssistantMessage, AssistantStatus } from '../lib/types';
import { Button } from './ui/button';

const STARTERS = [
  'What happened today?',
  'Why was attendance flagged?',
  'Which equipment is repeatedly missing?',
];

export default function AssistantDrawer({ open, onOpenChange, centreId }: { open: boolean; onOpenChange: (open: boolean) => void; centreId: string }) {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [sessionId, setSessionId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const sequence = useRef(0);

  useEffect(() => {
    if (!open) return;
    getAssistantStatus().then(setStatus).catch(() => setStatus({ enabled: true, configured: false, available: false, voice_configured: false, voice_available: false }));
  }, [open]);

  useEffect(() => {
    setMessages([]);
    setSessionId(undefined);
    setQuestion('');
    setError('');
  }, [centreId]);

  async function submitText(text: string) {
    const clean = text.trim();
    if (!clean || busy || status?.available === false) return;
    sequence.current += 1;
    const userId = `u-${sequence.current}`;
    setMessages(items => [...items, { id: userId, role: 'user', text: clean }]);
    setQuestion('');
    setBusy(true);
    setError('');
    try {
      const reply = await askAssistant(centreId, clean, sessionId);
      sequence.current += 1;
      setSessionId(reply.session_id);
      setMessages(items => [...items, { id: `a-${sequence.current}`, role: 'assistant', text: reply.message, sources: reply.sources }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assistant unavailable.');
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void submitText(question);
  }

  const configured = status?.configured !== false && status?.available !== false;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div className="fixed inset-0 z-40 bg-[#172033]/10" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-describedby="assistant-description">
              <motion.aside
                className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[420px] flex-col border-l border-[#E6EAF0] bg-white shadow-[0_12px_32px_rgba(16,24,40,.10)]"
                initial={{ x: 28, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 28, opacity: 0 }} transition={{ duration: 0.18, ease: 'easeOut' }}
              >
                <div className="flex items-start justify-between border-b border-[#EEF1F4] px-6 py-5">
                  <div>
                    <Dialog.Title className="text-xl font-medium text-[#172033]">KaushalWatch Assistant</Dialog.Title>
                    <Dialog.Description id="assistant-description" className="mt-1 text-[14px] text-[#667085]">Ask about available compliance evidence.</Dialog.Description>
                  </div>
                  <Dialog.Close asChild><Button variant="ghost" size="icon" aria-label="Close assistant"><X size={19} /></Button></Dialog.Close>
                </div>

                <div className="kw-scrollbar flex-1 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6" aria-live="polite" aria-busy={busy}>
                  {!configured ? (
                    <div className="rounded-2xl bg-[#F8FAFC] p-6">
                      <Bot size={21} className="text-[#667085]" />
                      <h3 className="mt-4 text-base font-medium text-[#172033]">Assistant unavailable</h3>
                      <p className="mt-2 text-[14px] leading-6 text-[#667085]">Assistant is not configured for this prototype. Evidence review remains available throughout KaushalWatch.</p>
                    </div>
                  ) : messages.length === 0 ? (
                    <div>
                      <div className="mb-8 rounded-2xl bg-[#F8FAFC] p-6">
                        <Bot size={21} className="text-[#2563EB]" />
                        <p className="mt-4 text-[15px] leading-6 text-[#475467]">I can explain recorded evidence and case history. Officers remain responsible for every final decision.</p>
                      </div>
                      <div className="text-[13px] font-medium text-[#667085]">Starter questions</div>
                      <div className="mt-3 space-y-2">
                        {STARTERS.map(item => <button key={item} type="button" onClick={() => void submitText(item)} className="kw-focus w-full rounded-xl border border-[#E6EAF0] bg-white px-4 py-3 text-left text-[14px] text-[#344054] transition-colors hover:bg-[#F8FAFC]">{item}</button>)}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      {messages.map(message => (
                        <div key={message.id} className={message.role === 'user' ? 'ml-10 rounded-2xl bg-[#EFF6FF] px-4 py-3 text-[14px] text-[#1D4ED8]' : 'mr-6 text-[14px] leading-6 text-[#344054]'}>
                          {message.text}
                          {message.role === 'assistant' && message.sources?.length ? <div className="mt-2 text-xs text-[#667085]">Grounded in {message.sources.length} recorded source{message.sources.length === 1 ? '' : 's'}.</div> : null}
                        </div>
                      ))}
                      {busy && <div className="flex items-center gap-2 text-[14px] text-[#667085]"><LoaderCircle size={16} className="animate-spin" /> Reviewing recorded evidence…</div>}
                    </div>
                  )}
                  {error && <div role="alert" className="mt-5 rounded-xl bg-[#FEF3F2] px-4 py-3 text-[14px] text-[#B42318]">{error}</div>}
                </div>

                <form onSubmit={submit} className="border-t border-[#EEF1F4] p-4">
                  <div className="flex items-end gap-2 rounded-2xl border border-[#D7DCE3] bg-white p-2 focus-within:border-[#93B4F6]">
                    <textarea aria-label="Ask assistant" placeholder="Ask about this centre…" rows={2} disabled={!configured || busy} value={question} onChange={event => setQuestion(event.target.value)} className="min-h-12 flex-1 resize-none border-0 bg-transparent px-2 py-2 text-[15px] leading-6 outline-none placeholder:text-[#98A2B3] disabled:bg-transparent" />
                    <Button type="submit" variant="primary" size="icon" disabled={!question.trim() || !configured || busy} aria-label="Send message"><ArrowUp size={18} /></Button>
                  </div>
                  <p className="mt-2 px-1 text-xs text-[#98A2B3]">AI surfaces evidence. Officers decide.</p>
                </form>
              </motion.aside>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
