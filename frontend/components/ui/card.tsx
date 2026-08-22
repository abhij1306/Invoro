import { Children, isValidElement } from 'react';
import type { ComponentPropsWithoutRef } from 'react';

import { cn } from '../../lib/utils';

/**
 * Card — bg-panel, border, --radius-lg, --card-padding, shadow-card.
 * Composed from header / title / description / content / footer slots.
 * Supports legacy `animate` prop for backward compatibility in Invoro.
 */
export function Card({
  children,
  className,
  animate,
  padded,
  ...props
}: Readonly<ComponentPropsWithoutRef<'section'> & { animate?: boolean; padded?: boolean }>) {
  const hasCompound = Children.toArray(children).some(
    (child) =>
      isValidElement(child) &&
      (child.type === CardHeader || child.type === CardContent || child.type === CardFooter),
  );
  const shouldPad = padded ?? !hasCompound;

  return (
    <section
      {...props}
      className={cn(
        'border-border bg-panel shadow-card rounded-lg border',
        shouldPad ? 'p-[var(--card-padding)]' : 'p-0',
        animate && 'animate-fade-in',
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  children,
  className,
  ...props
}: Readonly<ComponentPropsWithoutRef<'header'>>) {
  return (
    <header
      {...props}
      className={cn(
        'border-border-subtle flex flex-col gap-1 border-b p-[var(--card-padding)]',
        className,
      )}
    >
      {children}
    </header>
  );
}

export function CardTitle({
  children,
  className,
  ...props
}: Readonly<ComponentPropsWithoutRef<'h3'>>) {
  return (
    <h3 {...props} className={cn('text-foreground text-lg font-semibold', className)}>
      {children}
    </h3>
  );
}

export function CardDescription({
  children,
  className,
  ...props
}: Readonly<ComponentPropsWithoutRef<'p'>>) {
  return (
    <p {...props} className={cn('text-secondary text-sm', className)}>
      {children}
    </p>
  );
}

export function CardContent({
  children,
  className,
  ...props
}: Readonly<ComponentPropsWithoutRef<'div'>>) {
  return (
    <div {...props} className={cn('p-[var(--card-padding)]', className)}>
      {children}
    </div>
  );
}

export function CardFooter({
  children,
  className,
  ...props
}: Readonly<ComponentPropsWithoutRef<'footer'>>) {
  return (
    <footer
      {...props}
      className={cn(
        'border-border-subtle flex items-center gap-2 border-t p-[var(--card-padding)]',
        className,
      )}
    >
      {children}
    </footer>
  );
}
