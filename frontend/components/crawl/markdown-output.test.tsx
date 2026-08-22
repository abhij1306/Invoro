import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MarkdownOutput } from './markdown-output';

describe('MarkdownOutput', () => {
  it('keeps triple-star emphasis in paragraph parsing', () => {
    render(<MarkdownOutput markdown="***bold***" />);

    expect(screen.getByText('bold', { selector: 'strong' }).closest('p')).toBeInTheDocument();
  });

  it('renders a standalone triple-star line as a thematic break', () => {
    render(<MarkdownOutput markdown={'Before\n\n***\n\nAfter'} />);

    expect(screen.getByRole('separator')).toBeInTheDocument();
    expect(screen.getByText('After')).toBeInTheDocument();
  });
});
