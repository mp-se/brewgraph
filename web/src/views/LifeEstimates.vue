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
  <div v-if="modelValue && modelValue.readings > 0" class="row q-col-gutter-sm q-mb-sm">
    <div class="col-md-2">
      <AppReadonlyInput label="Est. ABV" :value="modelValue.abvString"></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput label="Days fermenting" :value="daysFermenting"></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput
        label="Avg interval"
        :value="modelValue.averageIntervalString"
      ></AppReadonlyInput>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: null
  }
})

const daysFermenting = computed(() => {
  if (!props.modelValue || !props.modelValue.date.first || !props.modelValue.date.last) return ''
  const ms = Date.parse(props.modelValue.date.last) - Date.parse(props.modelValue.date.first)
  const days = Math.floor(ms / (1000 * 60 * 60 * 24))
  return days + (days === 1 ? ' day' : ' days')
})
</script>
