<template>
  <div :class="['public-display', `theme-${context?.theme ?? 'dark'}`, { 'tv-mode': tvMode }]"
       :style="cssVars">
    <header class="display-header">
      <img v-if="context?.logoUrl" :src="context.logoUrl" alt="Venue logo" class="display-logo" />
      <div>
        <h1>{{ context?.breweryName ?? 'Tap List' }}</h1>
        <p>Live · {{ today }}</p>
      </div>
      <a :href="bottleRoute" class="display-link">Bottle menu</a>
    </header>

    <div v-if="loading" class="display-center"><div class="spinner" /></div>
    <div v-else-if="error" class="display-center muted">
      <span aria-hidden="true">⚠</span><p>{{ error }}</p>
    </div>
    <template v-else-if="taps.length">
      <main :class="['tap-grid', { 'tap-grid-tv': tvMode }]">
        <article v-for="(tap, index) in taps" :key="`${tap.tapName}:${index}`" class="display-card">
          <div class="tap-heading">
            <div class="tap-label">{{ tap.tapName }}</div>
            <div v-if="tap.serving" class="remaining">
              {{ tap.serving.volumeRemaining.toFixed(1) }} / {{ tap.serving.totalVolume.toFixed(1) }} L
            </div>
          </div>
          <template v-if="tap.serving">
            <h2>{{ tap.beerName }}</h2>
            <p v-if="tap.style" class="muted">{{ tap.style }}</p>
            <p class="stats">
              <span v-if="tap.abv != null">{{ tap.abv.toFixed(1) }}% ABV</span>
              <span v-if="tap.ibu != null"> · {{ Math.round(tap.ibu) }} IBU</span>
              <span v-if="tap.ebc != null"> · <i class="swatch" :style="{ background: ebcToHex(tap.ebc) }" />{{ Math.round(tap.ebc) }} EBC</span>
            </p>
            <div class="bar-track"><div class="bar-fill" :style="{ width: `${fillPercent(tap.serving)}%` }" /></div>
            <dl class="serving-readings">
              <div v-if="tap.serving.temperature != null" :class="{ stale: isStale(tap.serving.temperatureAt) }">
                <dt>Temperature</dt><dd>{{ tap.serving.temperature.toFixed(1) }} °C <small v-if="isStale(tap.serving.temperatureAt)">stale</small></dd>
              </div>
              <div v-if="tap.serving.pressure != null" :class="{ stale: isStale(tap.serving.pressureAt) }">
                <dt>Pressure</dt><dd>{{ tap.serving.pressure.toFixed(1) }} kPa <small v-if="isStale(tap.serving.pressureAt)">stale</small></dd>
              </div>
              <div v-if="tap.serving.lastPour">
                <dt>Last pour</dt><dd>{{ tap.serving.lastPour.amount.toFixed(1) }} L</dd>
              </div>
            </dl>
          </template>
          <p v-else class="empty">Available</p>
        </article>
      </main>
    </template>
    <div v-else class="display-center muted"><span aria-hidden="true">🍺</span><p>No taps on at the moment</p></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import axios from 'axios';

import {
  brandStyle, endpointUrl, fillPercent, isStale, type PublicTap,
} from '@/lib/publicDisplay';
import { useDisplayContext } from '@/lib/useDisplayContext';

const props = defineProps<{ token?: string }>();
const taps = ref<PublicTap[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
// Updated on every poll, so a display left running overnight shows today's date.
const now = ref(new Date());
let refreshTimer: ReturnType<typeof setInterval> | undefined;

const { context } = useDisplayContext(props.token);

const tvMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'tv');
const today = computed(() => now.value.toLocaleDateString());
const cssVars = computed(() => brandStyle(context.value));
const bottleRoute = computed(() => props.token
  ? `/public/${props.token}/bottles` : '/public/bottles');

async function fetchTaps() {
  now.value = new Date();
  try {
    const { data } = await axios.get<PublicTap[]>(endpointUrl('taps', props.token));
    taps.value = data;
    error.value = null;
  } catch {
    error.value = 'Display not found or unavailable.';
  } finally {
    loading.value = false;
  }
}

function ebcToHex(ebc: number): string {
  const colour = Math.min(Math.max(ebc * 0.508, 1), 40);
  return `rgb(${Math.round(Math.min(255, 204 - (colour - 1) * 3.5))},${Math.round(Math.max(0, 160 - (colour - 1) * 5))},${Math.round(Math.max(0, 60 - (colour - 1) * 2))})`;
}

onMounted(() => {
  void fetchTaps();
  refreshTimer = setInterval(() => { void fetchTaps(); }, 60_000);
});
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer); });
</script>
