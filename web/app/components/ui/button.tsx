import type { ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/cn';

const buttonVariants = cva(
  'kw-focus inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 text-[15px] font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45',
  {
    variants: {
      variant: {
        primary: 'bg-[#2563EB] text-white hover:bg-[#1D4ED8]',
        secondary: 'border border-[#E6EAF0] bg-white text-[#172033] hover:bg-[#F8FAFC]',
        ghost: 'text-[#475467] hover:bg-[#F2F4F7] hover:text-[#172033]',
        danger: 'border border-[#FECACA] bg-white text-[#B42318] hover:bg-[#FEF3F2]',
      },
      size: {
        default: 'h-11',
        sm: 'h-10 px-3.5',
        icon: 'h-10 w-10 px-0',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'default' },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
