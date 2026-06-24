import { describe, expect, it } from 'vitest';

import { resolveAutoSurface } from './auto-surface';

describe('resolveAutoSurface', () => {
  it('maps Codeforces homepage to content detail even in category mode', () => {
    const result = resolveAutoSurface('https://codeforces.com/', 'category');

    expect(result.surface).toBe('content_detail');
    expect(result.evidence).toContain('fallback_content_surface');
  });

  it('maps Codeforces blog entries to article detail', () => {
    const result = resolveAutoSurface('https://codeforces.com/blog/entry/153802', 'pdp');

    expect(result.surface).toBe('article_detail');
  });
});
