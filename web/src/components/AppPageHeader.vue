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
  <div class="row items-center app-page-header">
    <div :class="titleColClass">
      <p v-if="compact" class="text-subtitle2 q-mb-none">{{ title }}</p>
      <p v-else class="text-h6">{{ title }}</p>
    </div>
    <div v-if="$slots.action" class="col-auto app-page-header__action">
      <slot name="action"></slot>
    </div>
    <div v-if="$slots.default" :class="contentColClass">
      <slot></slot>
    </div>
  </div>
  <hr />
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue'

const props = withDefaults(defineProps<{ title: string; compact?: boolean }>(), {
  compact: false
})
const slots = useSlots()

// With a page action the title and the action share the first line (the action at the right), and
// any filters take the full line below; without one the filters sit beside the title.
const hasAction = computed(() => Boolean(slots.action))
const titleColClass = computed(() => (hasAction.value ? 'col' : props.compact ? 'col-md-4' : 'col-md-6'))
const contentColClass = computed(() =>
  hasAction.value ? 'col-12 app-page-header__filters' : props.compact ? 'col-md-8' : 'col-md-6'
)
</script>
