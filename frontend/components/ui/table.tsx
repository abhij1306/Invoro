'use client';

import type { CSSProperties, ReactNode, Ref, UIEventHandler } from 'react';

import { cn } from '../../lib/utils';

export function Table({
  children,
  className,
  wrapperClassName,
  wrapperRef,
  onWrapperScroll,
  style,
}: Readonly<{
  children: ReactNode;
  className?: string;
  wrapperClassName?: string;
  wrapperRef?: Ref<HTMLDivElement>;
  onWrapperScroll?: UIEventHandler<HTMLDivElement>;
  style?: CSSProperties;
}>) {
  return (
    <div
      ref={wrapperRef}
      onScroll={onWrapperScroll}
      className={cn('relative w-full overflow-auto', wrapperClassName)}
    >
      <table
        className={cn(
          'w-full border-separate border-spacing-0 text-[length:var(--table-font-size)]',
          className,
        )}
        style={style}
      >
        {children}
      </table>
    </div>
  );
}

export function TableHeader({
  children,
  className,
  ...props
}: Readonly<
  { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLTableSectionElement>
>) {
  return (
    <thead {...props} className={cn('[&_tr]:border-b', className)}>
      {children}
    </thead>
  );
}

export function TableBody({
  children,
  className,
  ...props
}: Readonly<
  { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLTableSectionElement>
>) {
  return (
    <tbody {...props} className={cn('[&_tr:last-child]:border-0', className)}>
      {children}
    </tbody>
  );
}

export function TableRow({
  children,
  className,
  ...props
}: Readonly<
  { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLTableRowElement>
>) {
  return (
    <tr
      {...props}
      className={cn(
        'border-border-subtle bg-panel hover:bg-background h-[var(--table-row-height)] border-b transition-colors',
        className,
      )}
    >
      {children}
    </tr>
  );
}

export function TableHead({
  children,
  className,
  ...props
}: Readonly<
  { children: ReactNode; className?: string } & React.ThHTMLAttributes<HTMLTableCellElement>
>) {
  // Data-table headers use the shared CSV-style mono header treatment.
  return (
    <th
      {...props}
      className={cn(
        'border-border bg-background text-muted sticky top-0 z-10 h-[var(--table-header-height)] px-3 text-left align-middle text-[length:var(--table-header-font-size)] font-semibold tracking-wide uppercase tabular-nums shadow-[inset_0_-1px_0_var(--border)]',
        className,
      )}
    >
      {children}
    </th>
  );
}

export function TableCell({
  children,
  className,
  colSpan,
  ...props
}: Readonly<
  {
    children?: ReactNode;
    className?: string;
    colSpan?: number;
  } & React.TdHTMLAttributes<HTMLTableCellElement>
>) {
  return (
    <td
      {...props}
      className={cn('text-secondary px-3 py-0 align-middle tabular-nums', className)}
      colSpan={colSpan}
    >
      {children}
    </td>
  );
}
