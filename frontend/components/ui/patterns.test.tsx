import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RunSummaryChips } from './patterns';

describe('RunSummaryChips', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uses stable semantic keys when chip values repeat', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<RunSummaryChips duration="0m 0s" verdict="unknown" quality="unknown" />);

    const duplicateKeyWarning = consoleSpy.mock.calls.some((call) =>
      call.some((entry) => String(entry).includes('Encountered two children with the same key')),
    );
    expect(duplicateKeyWarning).toBe(false);
  });
});
