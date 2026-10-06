<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph

  This file is part of BrewGraph. For open source use it is licensed under
  the GNU General Public License v3.0. For commercial use without source
  disclosure, a separate Commercial License is required.
  See LICENSE for details.
-->

<!--
  The one row-action control of every list screen: a compact filled icon button using the shared
  `AppButton` variant and density props, with a tooltip and an aria-label that both carry `label`.
  `kind` picks the colour by meaning and is the same on every screen: primary
  edits, negative deletes, positive opens gravity data, warning pressure data, info temperature
  data, and anything else (links, logs, exports, overflow) is secondary. Extra attributes (`to`,
  `disable`, `data-testid`, click handlers) fall through to the button, so a link row action is
  `to="..."`; a default slot takes a `q-menu` for an overflow trigger.
-->
<template>
  <app-button :variant="kind" dense class="app-row-action" :aria-label="label">
    <q-icon :name="icon" />
    <q-tooltip>{{ label }}</q-tooltip>
    <slot />
  </app-button>
</template>

<script setup lang="ts">
export type RowActionKind = 'primary' | 'negative' | 'positive' | 'warning' | 'info' | 'secondary'

withDefaults(defineProps<{ icon: string; label: string; kind?: RowActionKind }>(), {
  kind: 'secondary'
})
</script>
