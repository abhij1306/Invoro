'use client';

import type { KeyboardEvent, ReactNode } from 'react';

import { cn } from '../../../lib/utils';

type TabBarOption<T extends string> = { value: T; label: ReactNode; icon?: ReactNode };

export function TabBar<T extends string>({
  value,
  onChange,
  options,
  compact = false,
  className,
  variant = 'pill',
  size = 'md',
  fullWidth = false,
}: Readonly<{
  value: T;
  onChange: (value: T) => void;
  options: ReadonlyArray<TabBarOption<T>>;
  compact?: boolean;
  className?: string;
  variant?: 'pill' | 'underline';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}>) {
  const padX = compact
    ? size === 'sm'
      ? 'px-2'
      : 'px-2.5'
    : size === 'lg'
      ? 'px-4'
      : size === 'sm'
        ? 'px-2.5'
        : 'px-3';
  const heightClass =
    size === 'lg'
      ? 'h-[var(--control-height-lg)]'
      : size === 'sm'
        ? 'h-[var(--control-height-sm)]'
        : 'h-[var(--control-height)]';
  const gapClass = size === 'lg' ? 'gap-2' : 'gap-1.5';
  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const lastIndex = options.length - 1;
    let nextIndex: number | undefined;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      nextIndex = index === lastIndex ? 0 : index + 1;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      nextIndex = index === 0 ? lastIndex : index - 1;
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = lastIndex;
    }
    if (nextIndex === undefined || !options[nextIndex]) return;
    event.preventDefault();
    onChange(options[nextIndex].value);
    const tabs = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button');
    tabs?.[nextIndex]?.focus();
  };

  if (variant === 'underline') {
    return (
      <div
        role="group"
        aria-label="View options"
        className={cn(
          '-mb-px flex items-stretch bg-transparent p-0',
          heightClass,
          fullWidth && 'w-full',
          className,
        )}
      >
        {options.map((option, index) => (
          <button
            key={option.value}
            type="button"
            aria-current={value === option.value ? 'true' : undefined}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
            className={cn(
              'type-control relative -mb-px inline-flex shrink-0 items-center justify-center font-sans tracking-normal whitespace-nowrap transition-[border-color,color]',
              fullWidth && 'flex-1',
              padX,
              value === option.value
                ? 'border-accent text-accent border-b-2'
                : 'text-secondary hover:text-foreground hover:border-border border-b-2 border-transparent',
            )}
          >
            {tabBarOptionContent(option, gapClass)}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label="View options"
      className={cn(
        'border-border-subtle bg-background-alt inline-flex items-center gap-0.5 rounded-lg border p-0.5 shadow-none transition-[background-color,border-color,box-shadow]',
        heightClass,
        fullWidth && 'flex w-full',
        className,
      )}
    >
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          aria-current={value === option.value ? 'true' : undefined}
          onClick={() => onChange(option.value)}
          onKeyDown={(event) => handleTabKeyDown(event, index)}
          className={cn(
            'type-control relative z-10 inline-flex h-full min-w-[72px] shrink-0 items-center justify-center rounded-md font-sans text-sm tracking-normal whitespace-nowrap transition-[background-color,color,border-color,box-shadow] duration-150 ease-out select-none',
            fullWidth && 'flex-1',
            padX,
            value === option.value
              ? 'border-border bg-panel text-foreground border shadow-xs'
              : 'text-muted hover:text-foreground border border-transparent bg-transparent',
          )}
        >
          {tabBarOptionContent(option, gapClass)}
        </button>
      ))}
    </div>
  );
}

function tabBarOptionContent<T extends string>(option: TabBarOption<T>, gapClass: string) {
  if (!option.icon) return option.label;
  return (
    <span className={cn('inline-flex items-center', gapClass)}>
      <span className="shrink-0">{option.icon}</span>
      <span>{option.label}</span>
    </span>
  );
}

export function ProgressBar({ percent }: Readonly<{ percent: number }>) {
  const clampedPercent = Math.min(100, Math.max(0, percent));
  return (
    <div className="space-y-1">
      <div
        className="bg-background-alt h-1 overflow-hidden rounded-full"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clampedPercent}
      >
        <div
          className={cn(
            'bg-accent h-full rounded-full transition-[width] duration-500',
            clampedPercent >= 100 && 'bg-success',
          )}
          style={{ width: `${clampedPercent}%` }}
        />
      </div>
      <div className="type-caption-mono">{clampedPercent}%</div>
    </div>
  );
}
