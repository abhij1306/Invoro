'use client';

import * as React from 'react';
import { useId } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../../lib/utils';

const DROPDOWN_LISTBOX_ROLE = 'listbox';
const ESTIMATED_ITEM_HEIGHT_PX = 36;
const ESTIMATED_MENU_PADDING_PX = 8;

function sanitizeIdSegment(value: string) {
  const normalized = String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-');
  return normalized.replace(/^-+/g, '').replace(/-+$/g, '') || 'option';
}

export function Dropdown<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  id,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  className,
  triggerClassName,
  disabled = false,
  align = 'left',
  size = 'md',
  portal = true,
}: Readonly<{
  value: T;
  onChange: (value: T) => void;
  options: Array<{ value: T; label: string }>;
  ariaLabel?: string;
  id?: string;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean | 'true' | 'false';
  className?: string;
  triggerClassName?: string;
  disabled?: boolean;
  align?: 'left' | 'center';
  size?: 'sm' | 'md';
  portal?: boolean;
}>) {
  const [open, setOpen] = React.useState(false);
  const [highlightedIndex, setHighlightedIndex] = React.useState(-1);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const listboxRef = React.useRef<HTMLDivElement>(null);
  const [listboxPosition, setListboxPosition] = React.useState<{
    top: number;
    left: number;
    width: number;
    side: 'top' | 'bottom';
  }>({ top: 0, left: 0, width: 0, side: 'bottom' });
  const closeTimerRef = React.useRef<number | undefined>(undefined);
  const dropdownId = normalizedDropdownId(useId());
  const activeIndex = options.findIndex((o) => o.value === value);
  const listboxId = `${dropdownId}-listbox`;
  const activeDescendant = activeDescendantId(open, highlightedIndex, options, dropdownId);
  warnForMissingDropdownValue(value, activeIndex, options.length);

  function scheduleClose() {
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 120) as unknown as number;
  }

  function cancelClose() {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = undefined;
    }
  }

  const updatePosition = React.useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const menuHeight =
      listboxRef.current?.offsetHeight ??
      options.length * ESTIMATED_ITEM_HEIGHT_PX + ESTIMATED_MENU_PADDING_PX;
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const shouldFlip = spaceBelow < menuHeight && rect.top > menuHeight;

    setListboxPosition({
      top: shouldFlip ? rect.top - menuHeight - 4 : rect.bottom + 4,
      left: rect.left,
      width: rect.width,
      side: shouldFlip ? 'top' : 'bottom',
    });
  }, [options.length]);

  React.useLayoutEffect(() => {
    if (open) {
      let frameId: number | undefined;
      const schedulePositionUpdate = () => {
        if (frameId !== undefined) return;
        frameId = window.requestAnimationFrame(() => {
          frameId = undefined;
          updatePosition();
        });
      };
      schedulePositionUpdate();
      window.addEventListener('resize', schedulePositionUpdate);
      window.addEventListener('scroll', schedulePositionUpdate, { passive: true, capture: true });
      return () => {
        if (frameId !== undefined) window.cancelAnimationFrame(frameId);
        window.removeEventListener('resize', schedulePositionUpdate);
        window.removeEventListener('scroll', schedulePositionUpdate, { capture: true });
      };
    }
  }, [open, updatePosition]);

  React.useEffect(() => {
    const closeTimer = closeTimerRef;
    return () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, []);

  React.useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node) &&
        listboxRef.current &&
        !listboxRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (handleClosedDropdownKey(e, open, activeIndex, setHighlightedIndex, setOpen)) return;
    if (!open) return;
    handleOpenDropdownKey(e, options, highlightedIndex, setHighlightedIndex, setOpen, onChange);
  }

  const selectedLabel = selectedDropdownLabel(options, activeIndex, value);

  const listboxElement = (
    <DropdownListbox
      {...{
        listboxRef,
        listboxId,
        cancelClose,
        scheduleClose,
        portal,
        listboxPosition,
        options,
        dropdownId,
        value,
        highlightedIndex,
        onChange,
        setOpen,
        setHighlightedIndex,
        align,
      }}
    />
  );

  return (
    <div
      ref={containerRef}
      className={cn('relative', className)}
      onMouseEnter={() => {
        if (!disabled) {
          cancelClose();
          setHighlightedIndex(activeIndex >= 0 ? activeIndex : 0);
          setOpen(true);
        }
      }}
      onMouseLeave={() => {
        if (open) scheduleClose();
      }}
    >
      <button
        id={id}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
        aria-invalid={ariaInvalid}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-activedescendant={activeDescendant}
        onClick={() => {
          if (!open) setHighlightedIndex(activeIndex >= 0 ? activeIndex : 0);
          setOpen((current) => !current);
        }}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        className={dropdownTriggerClass(size, align, triggerClassName)}
      >
        <span className="truncate">{selectedLabel}</span>
        <svg
          className={cn(
            'text-muted size-3.5 shrink-0 transition-transform duration-150',
            open && 'rotate-180',
            align === 'center' ? 'absolute right-3' : 'relative',
          )}
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>
      {renderDropdownListbox(open, portal, listboxElement)}
    </div>
  );
}

function normalizedDropdownId(id: string) {
  return id.replace(/[^a-zA-Z0-9_-]+/g, '') || 'dropdown';
}

function activeDescendantId<T extends string>(
  open: boolean,
  index: number,
  options: Array<{ value: T }>,
  dropdownId: string,
) {
  if (!open || index < 0 || !options[index]) return undefined;
  return `${dropdownId}-option-${index}-${sanitizeIdSegment(options[index].value)}`;
}

function warnForMissingDropdownValue(value: string, activeIndex: number, optionCount: number) {
  if (process.env.NODE_ENV !== 'development' || activeIndex !== -1 || optionCount === 0) return;
  console.warn(`Dropdown: value "${value}" not found in options`);
}

function selectedDropdownLabel<T extends string>(
  options: Array<{ value: T; label: string }>,
  index: number,
  fallback: T,
) {
  return index >= 0 ? options[index].label : fallback;
}

function dropdownTriggerClass(size: 'sm' | 'md', align: 'left' | 'center', className?: string) {
  return cn(
    'focus-ring border-border bg-panel text-foreground hover:border-border-strong focus:border-accent flex w-full items-center gap-2 rounded-sm border px-3 leading-snug font-normal transition-[background-color,border-color]',
    size === 'sm' ? 'h-8 text-xs' : 'h-[var(--control-height)] text-sm',
    align === 'center' ? 'justify-center text-center' : 'justify-between text-left',
    className,
  );
}

function renderDropdownListbox(open: boolean, portal: boolean, element: React.ReactNode) {
  if (!open || typeof document === 'undefined') return null;
  return portal ? createPortal(element, document.body) : element;
}

function handleClosedDropdownKey(
  e: React.KeyboardEvent,
  open: boolean,
  activeIndex: number,
  setHighlightedIndex: React.Dispatch<React.SetStateAction<number>>,
  setOpen: React.Dispatch<React.SetStateAction<boolean>>,
) {
  if (open || !['Enter', ' ', 'ArrowDown'].includes(e.key)) return false;
  e.preventDefault();
  setHighlightedIndex(activeIndex >= 0 ? activeIndex : 0);
  setOpen(true);
  return true;
}

function handleOpenDropdownKey<T extends string>(
  e: React.KeyboardEvent,
  options: Array<{ value: T; label: string }>,
  highlightedIndex: number,
  setHighlightedIndex: React.Dispatch<React.SetStateAction<number>>,
  setOpen: React.Dispatch<React.SetStateAction<boolean>>,
  onChange: (value: T) => void,
) {
  if (['ArrowDown', 'ArrowUp'].includes(e.key) && options.length === 0) {
    e.preventDefault();
    return;
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    setHighlightedIndex((current) => (current < 0 ? 0 : (current + 1) % options.length));
    return;
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault();
    setHighlightedIndex((current) =>
      current < 0 ? 0 : (current - 1 + options.length) % options.length,
    );
    return;
  }
  if (!['Enter', ' '].includes(e.key)) return;
  e.preventDefault();
  const option = options[highlightedIndex];
  if (highlightedIndex >= 0 && option) onChange(option.value);
  setOpen(false);
}

type ListboxPosition = { top: number; left: number; width: number; side: 'top' | 'bottom' };

function DropdownListbox<T extends string>({
  listboxRef,
  listboxId,
  cancelClose,
  scheduleClose,
  portal,
  listboxPosition,
  options,
  dropdownId,
  value,
  highlightedIndex,
  onChange,
  setOpen,
  setHighlightedIndex,
  align,
}: {
  listboxRef: React.RefObject<HTMLDivElement | null>;
  listboxId: string;
  cancelClose: () => void;
  scheduleClose: () => void;
  portal: boolean;
  listboxPosition: ListboxPosition;
  options: Array<{ value: T; label: string }>;
  dropdownId: string;
  value: T;
  highlightedIndex: number;
  onChange: (value: T) => void;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setHighlightedIndex: React.Dispatch<React.SetStateAction<number>>;
  align: 'left' | 'center';
}) {
  return (
    <div
      ref={listboxRef}
      id={listboxId}
      role={DROPDOWN_LISTBOX_ROLE}
      tabIndex={-1}
      onMouseEnter={cancelClose}
      onMouseLeave={scheduleClose}
      className={cn(
        'border-border bg-background-elevated z-[300] max-h-[320px] w-max overflow-y-auto rounded-lg border py-1',
        portal ? 'fixed' : 'absolute',
        listboxPosition.side === 'bottom'
          ? 'animate-[dropdown-in_150ms_cubic-bezier(0.16,1,0.3,1)]'
          : 'animate-[dropdown-in-up_150ms_cubic-bezier(0.16,1,0.3,1)]',
      )}
      style={listboxStyle(portal, listboxPosition)}
    >
      {options.map((option, index) => (
        <DropdownOption
          key={option.value}
          {...{
            option,
            index,
            dropdownId,
            value,
            highlightedIndex,
            onChange,
            setOpen,
            setHighlightedIndex,
            align,
          }}
        />
      ))}
    </div>
  );
}

function listboxStyle(portal: boolean, position: ListboxPosition): React.CSSProperties {
  if (portal)
    return {
      top: `${position.top}px`,
      left: `${position.left}px`,
      minWidth: `${position.width}px`,
    };
  const opensTop = position.side === 'top';
  return {
    minWidth: '100%',
    top: opensTop ? 'auto' : '100%',
    bottom: opensTop ? '100%' : 'auto',
    transform: opensTop ? 'translateY(-4px)' : 'translateY(4px)',
  };
}

function DropdownOption<T extends string>({
  option,
  index,
  dropdownId,
  value,
  highlightedIndex,
  onChange,
  setOpen,
  setHighlightedIndex,
  align,
}: {
  option: { value: T; label: string };
  index: number;
  dropdownId: string;
  value: T;
  highlightedIndex: number;
  onChange: (value: T) => void;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setHighlightedIndex: React.Dispatch<React.SetStateAction<number>>;
  align: 'left' | 'center';
}) {
  const optionId = `${dropdownId}-option-${index}-${sanitizeIdSegment(option.value)}`;
  return (
    <button
      id={optionId}
      type="button"
      role="option"
      aria-selected={option.value === value}
      data-highlighted={index === highlightedIndex ? '' : undefined}
      onClick={() => {
        onChange(option.value);
        setOpen(false);
      }}
      onMouseDown={(e) => e.preventDefault()}
      onMouseEnter={() => setHighlightedIndex(index)}
      className={cn(
        'flex w-full items-center py-2 text-sm leading-snug transition-colors',
        align === 'center' ? 'justify-center px-8' : 'justify-start px-3',
        option.value === value
          ? 'bg-accent-subtle text-accent font-medium'
          : 'text-foreground hover:bg-background-alt data-[highlighted]:bg-background-alt',
      )}
    >
      {option.label}
    </button>
  );
}
