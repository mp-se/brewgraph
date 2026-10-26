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
  <label class="app-toggle">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="updateValue"
    />
    <span class="app-toggle__track" aria-hidden="true"></span>
    <span>{{ label }}</span>
  </label>
</template>

<script setup lang="ts">
defineProps<{ modelValue: boolean; label: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function updateValue(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).checked)
}
</script>
