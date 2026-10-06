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
  <div class="app-page app-page--fluid">
    <div style="height: 20px"></div>
    <div class="text-white text-center rounded-borders app-badge--primary" style="height: 30px">
      {{ text }}
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 2024-05-28 VueJS wrapper, Magnus Persson
 */

/**
 * Purpose: Provide a generic footer
 */

/**
 * Text to show in the footer (required).
 */
const text = defineModel<string>('text', { required: true })
</script>
