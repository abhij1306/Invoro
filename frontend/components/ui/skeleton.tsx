import { cn } from '../../lib/utils';

/** Skeleton loader — animate-pulse, rounded-md, bg-background-alt. */
export function Skeleton({ className }: Readonly<{ className?: string }>) {
  return (
    <div
      className={cn('skeleton bg-background-alt animate-pulse rounded-md', className)}
      aria-hidden="true"
    />
  );
}
