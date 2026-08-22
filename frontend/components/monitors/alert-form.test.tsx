import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AlertForm } from './alert-form';

describe('AlertForm', () => {
  it('preserves existing backend-supported fields and rules while editing', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const targetRules = [
      { path: 'inventory.quantity', label: 'Inventory', operator: 'changed' as const },
    ];

    render(
      <AlertForm
        initial={{
          id: 7,
          urls: ['https://example.com/products/widget'],
          tracked_fields: ['price', 'inventory_quantity'],
          target_rules: targetRules,
        }}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
        submitLabel="Save Alert"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Save Alert' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          target_fields: ['price', 'inventory_quantity'],
          target_rules: targetRules,
        }),
      );
    });
  });
});
