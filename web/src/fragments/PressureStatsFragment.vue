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
  <div v-if="modelValue" class="row q-col-gutter-sm q-mb-sm">
    <div class="col-md-2">
      <AppReadonlyInput
        label="Max pressure"
        :model-value="modelValue.pressure.maxString"
      ></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput
        label="Min pressure"
        :model-value="modelValue.pressure.minString"
      ></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput
        label="Temp min"
        :model-value="modelValue.temperature.minString"
      ></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput
        label="Temp max"
        :model-value="modelValue.temperature.maxString"
      ></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput
        label="Readings"
        :model-value="String(modelValue.readings)"
      ></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput label="First" :model-value="modelValue.date.firstDate"></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput label="Last" :model-value="modelValue.date.lastDate"></AppReadonlyInput>
    </div>
    <div class="col-md-2">
      <AppReadonlyInput
        label="Avg interval"
        :model-value="modelValue.averageIntervalString"
      ></AppReadonlyInput>
    </div>
  </div>
</template>

<script setup lang="ts">
interface DisplayRange {
  minString: string
  maxString: string
}

interface DisplayDates {
  firstDate: string
  lastDate: string
}

interface PressureStats {
  pressure: DisplayRange
  temperature: DisplayRange
  date: DisplayDates
  readings: number
  averageIntervalString: string
}

defineProps<{ modelValue: PressureStats | null }>()
</script>
