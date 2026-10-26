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
  <q-btn no-caps :class="buttonClasses" v-bind="$attrs">
    <slot />
  </q-btn>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Variant = 'primary' | 'secondary' | 'positive' | 'negative' | 'warning' | 'info' |
  'outline-primary' | 'outline-secondary' | 'outline-negative' | 'outline-positive'

const props = defineProps<{ variant?: Variant; dense?: boolean }>()

const buttonClasses = computed(() => [
  'app-button',
  props.variant && `app-button--${props.variant}`,
  props.dense && 'app-button--dense'
])
</script>
