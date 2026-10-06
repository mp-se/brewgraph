import { describe, expect, it } from 'vitest';

import {
  brandStyle, endpointUrl, fillPercent, isStale, themeStylesheetUrl,
} from '@/lib/publicDisplay';

describe('public display endpoint URLs', () => {
  it('uses tokenless OSS resource paths', () => {
    expect(endpointUrl('context')).toBe('/d');
    expect(endpointUrl('taps')).toBe('/t');
    expect(endpointUrl('bottles')).toBe('/b');
  });

  it('uses tokenized resource paths and encodes the token segment', () => {
    expect(endpointUrl('context', 'tenant-token')).toBe('/d/tenant-token');
    expect(endpointUrl('taps', 'tenant token')).toBe('/t/tenant%20token');
    expect(endpointUrl('bottles', 'tenant-token')).toBe('/b/tenant-token');
  });
});

describe('public serving helpers', () => {
  it('computes a bounded fill percentage client-side', () => {
    expect(fillPercent({ totalVolume: 20, volumeRemaining: 12.5 } as any)).toBe(62.5);
    expect(fillPercent({ totalVolume: 20, volumeRemaining: 25 } as any)).toBe(100);
    expect(fillPercent({ totalVolume: 0, volumeRemaining: 1 } as any)).toBe(0);
  });

  it('labels missing and old readings as stale', () => {
    const now = Date.parse('2026-09-13T12:00:00Z');
    expect(isStale(null, now)).toBe(true);
    expect(isStale('2026-09-13T11:49:59Z', now)).toBe(true);
    expect(isStale('2026-09-13T11:50:01Z', now)).toBe(false);
  });
});

describe('display branding', () => {
  const context = { breweryName: null, logoUrl: null, theme: 'dark' as const, primaryColor: null };

  it('leaves the theme colours alone without a brand colour', () => {
    expect(brandStyle(null)).toEqual({});
    expect(brandStyle(context)).toEqual({});
  });

  it('applies a brand colour to fills and primary text alike', () => {
    expect(brandStyle({ ...context, primaryColor: '#198754' })).toEqual({
      '--display-primary': '#198754',
      '--display-primary-text': '#198754',
    });
  });

  it('finds theme.css beside index.html wherever the bundle is served', () => {
    expect(themeStylesheetUrl('http://host/public/assets/index-abc.js'))
      .toBe('http://host/public/theme.css');
    expect(themeStylesheetUrl('http://display.local/assets/index-abc.js'))
      .toBe('http://display.local/theme.css');
  });
});
