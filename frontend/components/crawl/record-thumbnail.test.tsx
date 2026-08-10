import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RecordThumbnail } from './record-thumbnail';

describe('RecordThumbnail', () => {
  it('gives fill images a fixed-size parent', () => {
    render(<RecordThumbnail src="https://example.com/product.jpg" />);

    const frame = screen.getByTestId('record-thumbnail-frame');
    expect(frame).toHaveClass('relative', 'size-16', 'border');
    expect(frame.querySelector('img')).toHaveClass('object-contain');
  });
});
