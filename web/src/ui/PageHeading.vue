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
  <section class="app-page-heading">
    <div>
      <h1>{{ title }}</h1>
    </div>
    <div v-if="$slots.default" class="app-page-heading__actions">
      <slot />
    </div>
  </section>
  <hr class="app-page-divider" />
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>
