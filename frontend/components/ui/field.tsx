'use client';

import { cloneElement, isValidElement, useId } from 'react';
import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '../../lib/utils';

/**
 * Field — wraps a control with a label, optional hint, and an inline
 * error. Supports both standard nested child elements (for CrawlerAI backwards
 * compatibility) and the modern accessible render-prop pattern.
 */
export function Field({ label, hint, error, required, className, children }: Readonly<FieldProps>) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy =
    [error ? errorId : null, hint && !error ? hintId : null].filter(Boolean).join(' ') || undefined;

  const isRenderProp = typeof children === 'function';

  if (isRenderProp) {
    return (
      <div className={cn('grid gap-1.5', className)}>
        <label htmlFor={id} className="text-secondary text-sm font-medium">
          {label}
          {required ? <span className="text-danger ml-0.5">*</span> : null}
        </label>
        {children({
          id,
          'aria-invalid': error ? true : undefined,
          'aria-describedby': describedBy,
        })}
        {hint && !error ? (
          <span id={hintId} className="text-muted text-xs">
            {hint}
          </span>
        ) : null}
        {error ? (
          <span id={errorId} role="alert" className="text-danger-text text-xs">
            {error}
          </span>
        ) : null}
      </div>
    );
  }

  const control = isValidElement(children)
    ? cloneElement(children, {
        id,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': describedBy,
      } as HTMLAttributes<HTMLElement>)
    : children;

  // Backwards compatibility fallback with an explicit label and description.
  return (
    <div className={cn('grid gap-1.5', className)}>
      <label htmlFor={id} className="text-secondary cursor-text text-sm font-medium">
        {label}
        {required ? <span className="text-danger ml-0.5">*</span> : null}
      </label>
      {control}
      {hint && !error ? (
        <span id={hintId} className="text-muted text-xs">
          {hint}
        </span>
      ) : null}
      {error ? (
        <span id={errorId} role="alert" className="text-danger-text text-xs">
          {error}
        </span>
      ) : null}
    </div>
  );
}
export type FieldProps = {
  label: string;
  hint?: string;
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children:
    | ReactNode
    | ((props: { id: string; 'aria-invalid'?: boolean; 'aria-describedby'?: string }) => ReactNode);
};
