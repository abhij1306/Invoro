import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { NavTreeGroup } from './playground-normalizers';
import { NavTreePanel, PipelineStepCard } from './playground-panels';

const groups: NavTreeGroup[] = [
  {
    inputUrl: 'https://shop.example',
    source: 'homepage',
    tree: [
      {
        label: 'Men',
        children: [
          {
            label: 'Shorts',
            url: 'https://shop.example/men/shorts',
            children: [],
          },
          {
            label: 'Shirts',
            url: 'https://shop.example/men/shirts',
            children: [],
          },
        ],
      },
    ],
  },
];

function NavTreeHarness({
  onConfirm,
  treeGroups = groups,
}: {
  onConfirm?: (urls: string[]) => void;
  treeGroups?: NavTreeGroup[];
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const selectedUrls = Array.from(selected);

  return (
    <NavTreePanel
      groups={treeGroups}
      selected={selected}
      onToggleUrls={(urls) => {
        setSelected((prev) => {
          const next = new Set(prev);
          const allSelected = urls.every((url) => next.has(url));
          if (allSelected) urls.forEach((url) => next.delete(url));
          else urls.forEach((url) => next.add(url));
          return next;
        });
      }}
      onSelectAll={() =>
        setSelected(new Set(['https://shop.example/men/shorts', 'https://shop.example/men/shirts']))
      }
      onConfirm={() => onConfirm?.(selectedUrls)}
      confirmLabel={
        selected.size === 0
          ? 'Pick URL(s)'
          : `Crawl ${selected.size} URL${selected.size === 1 ? '' : 's'}`
      }
      confirmDisabled={selected.size === 0}
      isLoading={false}
    />
  );
}

describe('NavTreePanel', () => {
  it('selects descendant URLs when a parent is toggled', () => {
    render(<NavTreeHarness />);

    const checkboxes = screen
      .getAllByRole('checkbox')
      .filter((item): item is HTMLInputElement => item instanceof HTMLInputElement);
    fireEvent.click(checkboxes[0]);

    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[1]).toBeChecked();
    expect(checkboxes[2]).toBeChecked();
    expect(screen.getByRole('button', { name: /crawl 2 urls/i })).toBeEnabled();
  });

  it('shows parent indeterminate state for partial child selection', () => {
    render(<NavTreeHarness />);

    const checkboxes = screen
      .getAllByRole('checkbox')
      .filter((item): item is HTMLInputElement => item instanceof HTMLInputElement);
    fireEvent.click(checkboxes[1]);

    expect(checkboxes[0].indeterminate).toBe(true);
    expect(checkboxes[1]).toBeChecked();
    expect(checkboxes[2]).not.toBeChecked();
  });

  it('confirms selected flat category URLs', () => {
    const onConfirm = vi.fn();
    render(<NavTreeHarness onConfirm={onConfirm} />);

    const checkboxes = screen
      .getAllByRole('checkbox')
      .filter((item): item is HTMLInputElement => item instanceof HTMLInputElement);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole('button', { name: /crawl 1 url/i }));

    expect(onConfirm).toHaveBeenCalledWith(['https://shop.example/men/shorts']);
  });

  it('adds late-arriving top-level groups to the default open state', () => {
    const { rerender } = render(<NavTreeHarness treeGroups={[]} />);

    rerender(<NavTreeHarness treeGroups={groups} />);

    expect(screen.getByRole('checkbox', { name: 'Select Shorts' })).toBeVisible();
  });

  it('keeps leaf expand controls non-interactive and labels selection checkboxes', () => {
    render(<NavTreeHarness />);

    expect(screen.getAllByRole('button', { name: 'Collapse category' })).toHaveLength(1);
    expect(screen.getByRole('checkbox', { name: 'Select Men' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Select Shorts' })).toBeInTheDocument();
  });

  it('renders failed pipeline status with a danger badge', () => {
    render(<PipelineStepCard label="Extract" stepData={{ status: 'failed' }} />);

    expect(screen.getByText('Failed')).toHaveClass('text-danger-text');
  });
});
