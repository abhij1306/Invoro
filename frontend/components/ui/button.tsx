'use client';

import { forwardRef } from 'react';
import type { ComponentPropsWithoutRef, ElementRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { Slot } from '@radix-ui/react-slot';
import { cn } from '../../lib/utils';

export const buttonVariants = cva(
  'ui-button focus-ring inline-flex h-[var(--button-height)] items-center justify-center gap-1.5 rounded-[var(--radius-md)] border px-[var(--button-padding-x)] text-[length:var(--button-font-size)] font-sans font-medium leading-none whitespace-nowrap no-underline transition-[background-color,color,border-color,box-shadow] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 disabled:grayscale',
  {
    variants: {
      variant: {
        action: 'button-action-surface',
        download: 'button-download-surface',
        destructive: 'button-destructive-surface',
        neutral: 'button-neutral-surface',
        quiet: 'button-quiet-surface',
        topbar: 'button-topbar-surface',
        underline: 'button-link-surface',
        primary: 'button-action-surface',
        accent: 'button-action-surface',
        secondary: 'button-neutral-surface',
        ghost: 'button-quiet-surface',
        danger: 'button-destructive-surface',
      },
      size: {
        sm: 'ui-button-sm',
        md: 'ui-button-md',
        lg: 'ui-button-lg',
        icon: 'w-[var(--button-height)] px-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends ComponentPropsWithoutRef<'button'>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<ElementRef<'button'>, ButtonProps>(function Button(
  { className, variant, size, asChild = false, ...props }: ButtonProps,
  ref,
) {
  const Comp = asChild ? Slot : 'button';
  return <Comp ref={ref} {...props} className={cn(buttonVariants({ variant, size }), className)} />;
});
