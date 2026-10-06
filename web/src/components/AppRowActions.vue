<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<!-- The cell wrapper for a row's actions: keeps them on one line; a narrow table scrolls sideways instead. -->
<template>
  <div class="app-row-actions" role="group" :aria-label="label">
    <slot />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: 'Row actions' })
</script>

<style scoped>
.app-row-actions {
  display: inline-flex;
  flex-wrap: nowrap;
  white-space: nowrap;
  align-items: center;
  gap: 4px;
}
</style>
