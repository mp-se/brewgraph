import { onMounted, onUnmounted, ref } from 'vue';
import axios from 'axios';

import { endpointUrl, type PublicDisplayContext } from '@/lib/publicDisplay';

/** How often an open display re-reads its settings (theme, name, logo, colour). */
export const CONTEXT_REFRESH_MS = 5 * 60 * 1000;

/**
 * Display settings, kept current on a screen that is never reloaded.
 *
 * A failed fetch keeps whatever is on screen — the settings from the last
 * success, or the defaults. Settings are presentation only: a display whose
 * taps load should keep showing them, and a display that does not exist fails
 * its tap/bottle request, which reports the error.
 */
export function useDisplayContext(token: string | undefined) {
  const context = ref<PublicDisplayContext | null>(null);
  let timer: ReturnType<typeof setInterval> | undefined;

  async function fetchContext() {
    try {
      const { data } = await axios.get<PublicDisplayContext>(endpointUrl('context', token));
      context.value = data;
    } catch {
      // Keep the current settings; see above.
    }
  }

  onMounted(() => {
    void fetchContext();
    timer = setInterval(() => { void fetchContext(); }, CONTEXT_REFRESH_MS);
  });
  onUnmounted(() => { if (timer) clearInterval(timer); });

  return { context };
}
