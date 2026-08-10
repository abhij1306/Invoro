import { cva } from 'class-variance-authority';

const PRIMARY_VARIANT = 'border-transparent bg-accent text-accent-fg hover:bg-accent-hover';
const GHOST_VARIANT =
  'border-transparent bg-transparent text-secondary hover:bg-background-alt hover:text-foreground';
const DESTRUCTIVE_VARIANT = 'border-transparent bg-transparent text-danger-text hover:bg-danger-bg';

export const buttonVariants = cva(
  'focus-ring inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-sm border font-sans font-medium leading-none no-underline transition-[background-color,color,border-color,box-shadow] disabled:cursor-not-allowed disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: PRIMARY_VARIANT,
        secondary: 'border-border-strong bg-panel text-foreground hover:bg-background-alt',
        neutral: 'border-border bg-background-alt text-foreground hover:bg-panel-strong',
        ghost: GHOST_VARIANT,
        destructive: DESTRUCTIVE_VARIANT,
        topbar: GHOST_VARIANT,
        underline:
          'border-transparent bg-transparent text-accent-text underline hover:text-accent-hover',
        action: PRIMARY_VARIANT,
        accent: PRIMARY_VARIANT,
        quiet: GHOST_VARIANT,
        download: 'border-border bg-background-alt text-foreground hover:bg-panel-strong',
        danger: DESTRUCTIVE_VARIANT,
      },
      size: {
        sm: 'h-[var(--control-height-sm)] px-2.5 text-xs',
        md: 'h-[var(--control-height)] px-3.5 text-sm',
        lg: 'h-[var(--control-height-lg)] px-4 text-base',
        icon: 'size-[var(--control-height)] px-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);
