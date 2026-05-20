import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MonitorForm } from './monitor-form';

function renderMonitorForm() {
  render(
    <MonitorForm
      submitLabel="Save Monitor"
      onSubmit={vi.fn().mockResolvedValue(undefined)}
      onCancel={vi.fn()}
    />,
  );
}

describe('MonitorForm advanced settings', () => {
  it('keeps the advanced header padded and renders compact toggle rows', () => {
    renderMonitorForm();

    const advancedSwitch = screen.getByRole('switch', { name: 'Advanced crawl settings' });
    const advancedHeaderRow = advancedSwitch.closest('div.grid');

    expect(advancedHeaderRow).toHaveClass('px-3');
    expect(advancedHeaderRow).toHaveClass('py-2');

    fireEvent.click(advancedSwitch);

    const proxySwitch = screen.getByRole('switch', { name: 'Proxy' });
    const proxyRow = proxySwitch.closest('div.grid');

    expect(proxyRow).toHaveClass('h-9');
    expect(proxyRow).not.toHaveClass('border');
    expect(proxyRow).not.toHaveClass('px-3');
  });
});
