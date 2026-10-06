<template>
  <div :class="['public-display', `theme-${context?.theme ?? 'dark'}`, { 'tv-mode': tvMode }]"
       :style="cssVars">
    <header class="display-header">
      <img v-if="context?.logoUrl" :src="context.logoUrl" alt="Venue logo" class="display-logo" />
      <div><h1>{{ context?.breweryName ?? 'Bottle Menu' }}</h1><p>Packaged beer</p></div>
      <a :href="tapRoute" class="display-link">Tap list</a>
    </header>

    <div v-if="loading" class="display-center"><div class="spinner" /></div>
    <div v-else-if="error" class="display-center muted"><span aria-hidden="true">⚠</span><p>{{ error }}</p></div>
    <main v-else-if="bottles.length" :class="['tap-grid', { 'tap-grid-tv': tvMode }]">
      <article v-for="(bottle, index) in bottles" :key="`${bottle.beerName}:${index}`" class="display-card">
        <div class="tap-heading"><div class="tap-label">{{ bottle.availability }}</div><div class="remaining">{{ bottle.bottlesRemaining }} / {{ bottle.totalBottleCount }}</div></div>
        <h2>{{ bottle.beerName }}</h2>
        <p v-if="bottle.style" class="muted">{{ bottle.style }}</p>
        <p class="stats">
          <span v-if="bottle.abv != null">{{ bottle.abv.toFixed(1) }}% ABV</span>
          <span v-if="bottle.ibu != null"> · {{ Math.round(bottle.ibu) }} IBU</span>
          <span v-if="bottle.ebc != null"> · <i class="swatch" :style="{ background: ebcToHex(bottle.ebc) }" />{{ Math.round(bottle.ebc) }} EBC</span>
        </p>
        <p class="bottle-volume">{{ bottle.bottleVolume.toFixed(2) }} L bottles</p>
      </article>
    </main>
    <div v-else class="display-center muted"><span aria-hidden="true">🍺</span><p>No bottled beer available</p></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import axios from 'axios';

import { brandStyle, endpointUrl, type PublicBottle } from '@/lib/publicDisplay';
import { useDisplayContext } from '@/lib/useDisplayContext';

const props = defineProps<{ token?: string }>();
const bottles = ref<PublicBottle[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
let refreshTimer: ReturnType<typeof setInterval> | undefined;

const { context } = useDisplayContext(props.token);

const tvMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'tv');
const cssVars = computed(() => brandStyle(context.value));
const tapRoute = computed(() => props.token ? `/public/${props.token}` : '/public');

async function fetchBottles() {
  try {
    const { data } = await axios.get<PublicBottle[]>(endpointUrl('bottles', props.token));
    bottles.value = data;
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
  void fetchBottles();
  refreshTimer = setInterval(() => { void fetchBottles(); }, 60_000);
});
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer); });
</script>
