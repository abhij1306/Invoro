import { describe, expect, it } from 'vitest';

import { isDemoDisabledPath } from './demo-mode';

describe('AWS demo mode routes', () => {
  it('blocks registration and monitoring pages', () => {
    expect(isDemoDisabledPath('/register')).toBe(true);
    expect(isDemoDisabledPath('/monitors')).toBe(true);
    expect(isDemoDisabledPath('/monitors/42')).toBe(true);
    expect(isDemoDisabledPath('/alerts/new')).toBe(true);
    expect(isDemoDisabledPath('/crawl')).toBe(false);
    expect(isDemoDisabledPath('/selectors')).toBe(false);
  });
});
