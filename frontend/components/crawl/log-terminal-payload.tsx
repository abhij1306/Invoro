'use client';

import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Copy } from 'lucide-react';
import React from 'react';

import { cleanRecordForDisplay } from '../../lib/crawl/record-utils';
import { syntaxHighlightJsonNodes } from '../../lib/ui/syntax';
import { Button } from '../ui/primitives';
import { TERMINAL_STRINGS } from './log-terminal-utils';
import type { LogSiteGroup } from './log-terminal-utils';

export function PayloadPeekPanel({
  activePeekedGroupKey,
  peekPanelRef,
  peekReturnFocusRef,
  peekedGroup,
  safePeekedRecordIndex,
  peekedRecordJson,
  setPeekedGroupKey,
}: {
  activePeekedGroupKey: string | null;
  peekPanelRef: React.RefObject<HTMLDivElement | null>;
  peekReturnFocusRef: React.RefObject<HTMLElement | null>;
  peekedGroup: LogSiteGroup | null;
  safePeekedRecordIndex: number;
  peekedRecordJson: string;
  setPeekedGroupKey: React.Dispatch<React.SetStateAction<string | null>>;
}) {
  React.useEffect(() => {
    if (!activePeekedGroupKey) return;
    const returnFocus = peekReturnFocusRef.current;
    return () => returnFocus?.focus();
  }, [activePeekedGroupKey, peekReturnFocusRef]);

  if (!activePeekedGroupKey) return null;
  return (
    <DialogPrimitive.Root
      open
      onOpenChange={(open) => {
        if (!open) setPeekedGroupKey(null);
      }}
    >
      <DialogPrimitive.Overlay className="absolute inset-0 z-40 bg-[color-mix(in_srgb,var(--bg-base)_60%,transparent)] backdrop-blur-sm" />
      <DialogPrimitive.Content
        ref={peekPanelRef}
        aria-describedby={undefined}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          peekReturnFocusRef.current?.focus();
        }}
        className="animate-in slide-in-from-right absolute inset-y-0 right-0 z-50 w-[36rem] max-w-full border-l duration-300"
        style={{
          borderColor: 'var(--terminal-border)',
          backgroundColor: 'var(--terminal-code-bg)',
          color: 'var(--terminal-fg)',
          boxShadow: 'var(--terminal-shadow)',
        }}
      >
        <div
          className="flex items-center justify-between border-b px-6 py-3"
          style={{
            borderColor: 'var(--terminal-border)',
            backgroundColor: 'var(--terminal-bg)',
          }}
        >
          <div className="min-w-0 flex-1">
            <DialogPrimitive.Title className="text-accent type-label-mono m-0">
              {TERMINAL_STRINGS.PAYLOAD_PEEK}
            </DialogPrimitive.Title>
            <div
              className="mt-0.5 truncate pr-4 text-xs font-medium tabular-nums"
              style={{ color: 'var(--text-muted)' }}
              title={peekedGroup?.label ?? ''}
            >
              {peekedGroup?.label ?? TERMINAL_STRINGS.SITE_PAYLOAD}
            </div>
          </div>
          <DialogPrimitive.Close asChild>
            <Button type="button" variant="quiet" size="sm">
              Close
            </Button>
          </DialogPrimitive.Close>
        </div>
        <div className="relative h-[calc(100%-56px)] overflow-hidden p-6">
          <div className="group relative h-full">
            <div className="absolute top-3 right-3 z-10 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
              <Button
                type="button"
                variant="quiet"
                size="sm"
                onClick={() => {
                  if (!peekedGroup) return;
                  const currentRecord =
                    peekedGroup.records[safePeekedRecordIndex] ?? peekedGroup.records[0];
                  if (!currentRecord) return;
                  void navigator.clipboard.writeText(
                    JSON.stringify(cleanRecordForDisplay(currentRecord), null, 2),
                  );
                }}
              >
                <Copy className="mr-1.5 size-3" />
                Copy
              </Button>
            </div>
            {peekedRecordJson ? (
              <pre className="crawl-terminal crawl-terminal-json h-full max-h-full overflow-auto">
                <span className="sr-only">{peekedRecordJson}</span>
                <span aria-hidden="true">{syntaxHighlightJsonNodes(peekedRecordJson)}</span>
              </pre>
            ) : (
              <pre className="crawl-terminal crawl-terminal-json h-full max-h-full overflow-auto">
                {TERMINAL_STRINGS.NO_PAYLOAD}
              </pre>
            )}
          </div>
        </div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Root>
  );
}
