<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<!--
  A round dot, so it is not mistaken for a checkbox. An item without a colour gets no dot at all (and
  none of the spacing a caller's class would add).
-->
<template>
  <span
    v-if="color"
    class="device-color-swatch inline-block vertical-middle no-shrink"
    :style="{ backgroundColor: color, width: size, height: size }"
    role="img"
    :aria-label="`${label} device color`"
    :title="`${label} device color`"
  ></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ color?: string | null; size?: string }>(), {
  color: undefined,
  size: '1rem'
})

const label = computed(() => (props.color ?? '').charAt(0).toUpperCase() + (props.color ?? '').slice(1))
</script>

<style scoped>
.device-color-swatch {
  border-radius: 50%;
  /* A hairline ring keeps a white or black dot visible on either theme without looking like a box. */
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--app-swatch-outline) 45%, transparent);
}
</style>
