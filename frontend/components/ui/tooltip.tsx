'use client';

import * as React from 'react';
import { useId } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

/**
 * Tooltip — Portal-based positioning to prevent clipping.
 * Styled with the dense panel-strong surface, text-xs, and border-strong tokens.
 */
export function Tooltip({
  children,
  content,
  className,
  align = 'center',
}: Readonly<{
  children: ReactNode;
  content: string;
  className?: string;
  align?: 'center' | 'start';
}>) {
  const tooltipId = useId();
  const childArray = React.Children.toArray(children);
  const child =
    childArray.length === 1 && React.isValidElement(childArray[0]) ? childArray[0] : null;
  const anchorRef = React.useRef<HTMLDivElement>(null);
  const tooltipRef = React.useRef<HTMLDivElement>(null);
  const closeTimerRef = React.useRef<number | undefined>(undefined);
  const [open, setOpen] = React.useState(false);
  const [position, setPosition] = React.useState<{ left: number; top: number }>({
    left: 0,
    top: 0,
  });
  const [placement, setPlacement] = React.useState<'top' | 'bottom'>('top');
  const enhancedChild = child ? (
    React.cloneElement(child, {
      'aria-describedby': open ? tooltipId : undefined,
    } as React.HTMLAttributes<HTMLElement>)
  ) : (
    <span>{children}</span>
  );

  function cancelClose() {
    if (closeTimerRef.current !== undefined) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = undefined;
    }
  }

  function scheduleClose() {
    cancelClose();
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 100);
  }

  const updatePosition = React.useCallback(() => {
    if (!anchorRef.current || !tooltipRef.current) {
      return;
    }
    const anchorRect = anchorRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const margin = 12;
    const idealLeft =
      align === 'start'
        ? anchorRect.left
        : anchorRect.left + anchorRect.width / 2 - tooltipRect.width / 2;
    const maxLeft = window.innerWidth - tooltipRect.width - margin;
    const nextLeft = Math.min(Math.max(idealLeft, margin), Math.max(margin, maxLeft));
    const gap = 8;
    const fitsAbove = anchorRect.top - tooltipRect.height - gap >= margin;
    const nextPlacement = fitsAbove ? 'top' : 'bottom';
    const nextTop = fitsAbove
      ? anchorRect.top - tooltipRect.height - gap
      : Math.min(window.innerHeight - tooltipRect.height - margin, anchorRect.bottom + gap);
    setPlacement(nextPlacement);
    setPosition({ left: nextLeft, top: nextTop });
  }, [align, setPosition]);
  const updatePositionEvent = React.useEffectEvent(updatePosition);

  React.useLayoutEffect(() => {
    if (!open) {
      return;
    }
    updatePosition();
  }, [open, content, updatePosition]);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    const handleLayout = () => updatePositionEvent();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('resize', handleLayout);
    window.addEventListener('scroll', handleLayout, true);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('resize', handleLayout);
      window.removeEventListener('scroll', handleLayout, true);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  React.useEffect(() => {
    const closeTimer = closeTimerRef;
    return () => {
      if (closeTimer.current !== undefined) window.clearTimeout(closeTimer.current);
    };
  }, []);

  return (
    <div
      ref={anchorRef}
      className={cn('relative flex items-center', className)}
      onMouseEnter={() => {
        cancelClose();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
      onFocus={() => setOpen(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOpen(false);
        }
      }}
    >
      {enhancedChild}
      {open && typeof document !== 'undefined'
        ? createPortal(
            <div
              ref={tooltipRef}
              id={tooltipId}
              role="tooltip"
              onMouseEnter={cancelClose}
              onMouseLeave={scheduleClose}
              className={cn(
                'fixed w-max max-w-[min(320px,calc(100vw-24px))]',
                'bg-panel-strong border-border-strong rounded-md border px-2 py-1 shadow-sm',
                'text-foreground z-[200] text-xs leading-normal font-medium break-words',
              )}
              style={{ left: `${position.left}px`, top: `${position.top}px` }}
            >
              {content}
              <div
                className={cn(
                  'border-border-strong bg-panel-strong absolute size-2.5',
                  placement === 'top'
                    ? '-bottom-[5px] border-r border-b'
                    : '-top-[5px] border-t border-l',
                )}
                style={{
                  left: align === 'start' ? '12px' : '50%',
                  transform: align === 'start' ? 'rotate(45deg)' : 'translateX(-50%) rotate(45deg)',
                }}
              />
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
