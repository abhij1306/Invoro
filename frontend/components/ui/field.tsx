'use client';

import { cloneElement, isValidElement, useId } from 'react';
import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '../../lib/utils';

/**
 * Field — wraps a control with a label, optional hint, and an inline
 * error. Supports both standard nested child elements (for Invoro backwards
 * compatibility) and the modern accessible render-prop pattern.
 */
export function Field({ label, hint, error, required, className, children }: Readonly<FieldProps>) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy =
    [error ? errorId : null, hint && !error ? hintId : null].filter(Boolean).join(' ') || undefined;

  if (typeof children === 'function') {
    return (
      <RenderPropField
        {...{ label, hint, error, required, className, id, hintId, errorId, describedBy }}
      >
        {children}
      </RenderPropField>
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

type FieldFrameProps = Pick<FieldProps, 'label' | 'hint' | 'error' | 'required' | 'className'> & {
  id: string;
  hintId: string;
  errorId: string;
  describedBy?: string;
};

function RenderPropField({
  children,
  ...frame
}: FieldFrameProps & { children: Exclude<FieldProps['children'], ReactNode> }) {
  const { id, describedBy } = frame;
  return (
    <div className={cn('grid gap-1.5', frame.className)}>
      <FieldLabel {...frame} />
      {children({
        id,
        'aria-invalid': frame.error ? true : undefined,
        'aria-describedby': describedBy,
      })}
      <FieldDescription {...frame} />
    </div>
  );
}

function FieldLabel({ id, label, required }: FieldFrameProps) {
  return (
    <label htmlFor={id} className="text-secondary text-sm font-medium">
      {label}
      {required ? <span className="text-danger ml-0.5">*</span> : null}
    </label>
  );
}

function FieldDescription({ hint, error, hintId, errorId }: FieldFrameProps) {
  if (error) {
    return (
      <span id={errorId} role="alert" className="text-danger-text text-xs">
        {error}
      </span>
    );
  }
  return hint ? (
    <span id={hintId} className="text-muted text-xs">
      {hint}
    </span>
  ) : null;
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
