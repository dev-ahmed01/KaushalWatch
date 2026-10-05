'use client';
import { Check, X } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

export default function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return <AnimatePresence>{message ? <motion.div role="status" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }} className="fixed bottom-6 right-6 z-[80] flex max-w-sm items-start gap-3 rounded-2xl border border-[#E6EAF0] bg-white px-4 py-3 shadow-[0_12px_32px_rgba(16,24,40,.10)]"><span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-[#ECFDF3] text-[#067647]"><Check size={14} /></span><div className="flex-1 text-[14px] text-[#344054]">{message}</div><button type="button" onClick={onClose} className="kw-focus rounded-md p-1 text-[#98A2B3] hover:text-[#344054]" aria-label="Dismiss"><X size={14} /></button></motion.div> : null}</AnimatePresence>;
}
