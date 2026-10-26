<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph

  This file is part of BrewGraph. For open source use it is licensed under
  the GNU General Public License v3.0. For commercial use without source
  disclosure, a separate Commercial License is required.
  See LICENSE for details.
-->

<template>
  <section class="app-panel" :class="tone ? `app-panel--${tone}` : undefined">
    <header v-if="title" class="app-panel__title">
      {{ title }}
    </header>
    <div class="app-panel__divider"></div>
    <div class="app-panel__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title?: string; tone?: 'primary' | 'success' | 'info' | 'danger' | 'secondary' }>()
</script>
