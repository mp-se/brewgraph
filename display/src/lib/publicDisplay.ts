export type Resource = 'context' | 'taps' | 'bottles';

export interface PublicDisplayContext {
  breweryName: string | null;
  logoUrl: string | null;
  theme: 'dark' | 'light' | 'chalkboard' | 'minimal';
  primaryColor: string | null;
}

export interface PublicLastPour {
  at: string;
  amount: number;
  volumeRemaining: number;
}

export interface PublicServing {
  servingSince: string;
  totalVolume: number;
  volumeRemaining: number;
  volumePoured: number;
  temperature: number | null;
  temperatureAt: string | null;
  pressure: number | null;
  pressureAt: string | null;
  lastPour: PublicLastPour | null;
}

export interface PublicTap {
  tapName: string;
  beerName?: string;
  style?: string;
  abv?: number;
  ibu?: number;
  ebc?: number;
  serving: PublicServing | null;
}

export interface PublicBottle {
  beerName: string;
  style?: string;
  abv?: number;
  ibu?: number;
  ebc?: number;
  bottleVolume: number;
  bottlesRemaining: number;
  totalBottleCount: number;
  availability: 'available';
}

const resourcePath: Record<Resource, string> = {
  context: 'd',
  taps: 't',
  bottles: 'b',
};

export function endpointUrl(resource: Resource, token?: string): string {
  const base = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
  const suffix = token ? `/${encodeURIComponent(token)}` : '';
  return `${base}/${resourcePath[resource]}${suffix}`;
}

export function fillPercent(serving: PublicServing): number {
  if (serving.totalVolume <= 0) return 0;
  return Math.max(0, Math.min(100, (serving.volumeRemaining / serving.totalVolume) * 100));
}

export function isStale(observedAt: string | null, now = Date.now()): boolean {
  return !observedAt || now - new Date(observedAt).getTime() > 10 * 60 * 1000;
}

/**
 * Inline style for the configured brand colour. It sets the primary text colour
 * too, so a theme's own text tint (dark uses a lighter blue) never shows beside it.
 */
export function brandStyle(context: PublicDisplayContext | null): Record<string, string> {
  const color = context?.primaryColor;
  return color ? { '--display-primary': color, '--display-primary-text': color } : {};
}

/**
 * Where the deployment-replaceable `theme.css` lives: beside index.html. It is
 * resolved from this module's own URL (in assets/), not from the page URL, so it
 * is found the same way on every route, /public/<token>/bottles included.
 */
export function themeStylesheetUrl(moduleUrl: string): string {
  const path = '../theme.css';
  return new URL(path, moduleUrl).href;
}
