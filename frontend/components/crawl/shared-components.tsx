'use client';

import type { ReactNode } from 'react';

import { cn } from '../../lib/utils';
import { Button } from '../ui/primitives';

export {
  AdditionalFieldInput,
  CsvFileField,
  FieldEditorHeader,
  ManualFieldEditor,
  SettingSection,
  SliderRow,
  SitemapConfigFields,
  TargetUrlField,
} from './form-fields';
export { LogTerminal } from './log-terminal';
export { RecordThumbnail } from './record-thumbnail';
export { RecordsTable } from './records-table';

export function ActionButton({
  label,
  danger,
  disabled,
  onClick,
}: Readonly<{ label: string; danger?: boolean; disabled?: boolean; onClick?: () => void }>) {
  return (
    <Button
      variant={danger ? 'destructive' : 'neutral'}
      size="sm"
      disabled={disabled}
      onClick={onClick}
      className="min-w-0"
    >
      {label}
    </Button>
  );
}

export function PreviewRow({
  label,
  value,
  mono,
}: Readonly<{ label: string; value: ReactNode; mono?: boolean }>) {
  return (
    <div className="surface-muted flex items-start justify-between gap-4 rounded-md px-3 py-2">
      <div className="field-label shrink-0">{label}</div>
      <div
        className={cn(
          'type-body-sm text-foreground min-w-0 flex-1 text-right font-normal',
          mono && 'type-caption-mono !text-foreground font-medium',
        )}
      >
        {value || '--'}
      </div>
    </div>
  );
}
