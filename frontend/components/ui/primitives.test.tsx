import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Dropdown, Field, Skeleton, Toggle, Tooltip } from './primitives';

describe('Dropdown', () => {
  it('sanitizes option IDs and correctly manages aria-activedescendant for accessibility', () => {
    const handleChange = vi.fn();

    render(
      <Dropdown
        ariaLabel="Surface"
        value="jobs / detail"
        onChange={handleChange}
        options={[
          { value: 'jobs / detail', label: 'Jobs Detail' },
          { value: 'commerce:listing', label: 'Commerce Listing' },
        ]}
      />,
    );

    const combobox = screen.getByRole('combobox', { name: 'Surface' });
    fireEvent.click(combobox);
    const listbox = screen.getByRole('listbox');
    const activeDescendant = combobox.getAttribute('aria-activedescendant');
    const activeOption = screen.getByRole('option', { name: 'Jobs Detail' });
    expect(activeOption.id).toMatch(/jobs-detail$/);
    expect(activeOption.id).not.toBe('jobs / detail');
    expect(activeOption.id).not.toBe('');
    expect(activeOption.id).not.toContain(' ');
    expect(combobox).toHaveAttribute('aria-activedescendant', activeOption.id);
    expect(listbox).not.toHaveAttribute('aria-activedescendant');
    expect(document.getElementById(activeDescendant ?? '')).toBe(activeOption);

    const otherOption = screen.getByRole('option', { name: 'Commerce Listing' });
    expect(otherOption.id).toMatch(/commerce-listing$/);
    expect(otherOption.id).not.toBe('');
    expect(otherOption.id).not.toContain(' ');
  });

  it('highlights with arrow keys and commits only on Enter', () => {
    const handleChange = vi.fn();
    render(
      <Dropdown
        ariaLabel="Surface"
        value="first"
        onChange={handleChange}
        options={[
          { value: 'first', label: 'First' },
          { value: 'second', label: 'Second' },
        ]}
      />,
    );

    const combobox = screen.getByRole('combobox', { name: 'Surface' });
    fireEvent.click(combobox);
    fireEvent.keyDown(combobox, { key: 'ArrowDown' });
    expect(handleChange).not.toHaveBeenCalled();
    fireEvent.keyDown(combobox, { key: 'Enter' });
    expect(handleChange).toHaveBeenCalledWith('second');
  });

  it('handles arrow keys with no options', () => {
    const handleChange = vi.fn();
    render(<Dropdown ariaLabel="Empty" value="none" onChange={handleChange} options={[]} />);

    const combobox = screen.getByRole('combobox', { name: 'Empty' });
    fireEvent.click(combobox);
    expect(() => fireEvent.keyDown(combobox, { key: 'ArrowUp' })).not.toThrow();
    expect(handleChange).not.toHaveBeenCalled();
  });
});

describe('Tooltip', () => {
  it('supports text children and dismisses with Escape', () => {
    render(<Tooltip content="Helpful context">Plain trigger</Tooltip>);

    const trigger = screen.getByText('Plain trigger');
    fireEvent.mouseEnter(trigger);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});

describe('Field', () => {
  it('associates labels and descriptions with custom dropdown controls', () => {
    render(
      <Field label="Surface" hint="Choose a crawl surface">
        <Dropdown
          value="commerce"
          onChange={vi.fn()}
          options={[{ value: 'commerce', label: 'Commerce' }]}
        />
      </Field>,
    );

    const combobox = screen.getByRole('combobox', { name: 'Surface' });
    expect(combobox.id).not.toBe('');
    expect(screen.getByText('Surface')).toHaveAttribute('for', combobox.id);
    expect(combobox).toHaveAccessibleDescription('Choose a crawl surface');
  });
});

describe('Toggle', () => {
  it('uses dedicated track tokens instead of button accent tokens', () => {
    const handleChange = vi.fn();

    const { rerender } = render(
      <Toggle checked={false} onChange={handleChange} ariaLabel="Proxy" />,
    );

    const toggle = screen.getByRole('switch', { name: 'Proxy' });
    expect(toggle).toHaveClass('toggle-track-off');
    expect(toggle).not.toHaveClass('bg-accent');

    rerender(<Toggle checked={true} onChange={handleChange} ariaLabel="Proxy" />);

    expect(toggle).toHaveClass('toggle-track-on');
    expect(toggle).not.toHaveClass('bg-accent');
  });
});

describe('Skeleton', () => {
  it('stays purely decorative for assistive tech', () => {
    render(<Skeleton className="h-4 w-12" />);

    const skeleton = document.querySelector('.skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});
