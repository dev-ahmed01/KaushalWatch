import Link from 'next/link';
import { ArrowLeft, SearchX } from 'lucide-react';
import { buttonVariants } from './components/ui/button';

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-xl items-center justify-center px-4">
      <div className="w-full rounded-[18px] border border-[#E6EAF0] bg-white p-7 text-center shadow-[var(--kw-shadow)]">
        <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-[#F2F4F7] text-[#667085]">
          <SearchX size={20} />
        </span>
        <h1 className="mt-4 text-[22px] font-semibold tracking-[-0.03em] text-[var(--kw-text)]">Page not found</h1>
        <p className="mt-2 text-[13px] leading-6 text-[#667085]">
          The requested KaushalWatch view does not exist or is no longer part of the active workflow.
        </p>
        <Link href="/" className={buttonVariants({ variant: 'primary', className: 'mt-5' })}>
          <ArrowLeft size={15} />
          Back to KaushalAI
        </Link>
      </div>
    </div>
  );
}
