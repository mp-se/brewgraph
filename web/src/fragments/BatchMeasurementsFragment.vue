<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->
<template>
  <section aria-label="Measurements">
    <div v-if="visibleViews.length > 1" class="app-button-group q-mb-md" role="group" aria-label="Measurement views">
      <app-button
        v-for="view in visibleViews"
        :key="view.value"
        type="button"
        :variant="measurementView === view.value ? 'primary' : 'outline-secondary'"
        :aria-pressed="measurementView === view.value"
        :aria-label="view.label + (hasData[view.value] ? ', has readings' : '')"
        @click="selectMeasurementView(view.value)"
      >
        {{ view.label }}<span v-if="hasData[view.value]" class="measurement-data-dot q-ml-xs" aria-hidden="true"></span>
      </app-button>
    </div>
    <component :is="measurementComponent" :key="measurementView" />
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import type { Batch } from '@/modules/classes'
import router from '@/modules/router'

type MeasurementView = 'gravity' | 'pressure' | 'temp'
const props = defineProps<{ batch: Batch }>()
const measurementViews = [
  { label: 'Gravity', value: 'gravity' as const },
  { label: 'Pressure', value: 'pressure' as const },
  { label: 'Temp', value: 'temp' as const }
]
const components = {
  gravity: defineAsyncComponent(() => import('@/views/BatchGravityGraphView.vue').then((module) => module.default)),
  pressure: defineAsyncComponent(() => import('@/views/BatchPressureGraphView.vue').then((module) => module.default)),
  temp: defineAsyncComponent(() => import('@/views/BatchTempChartView.vue').then((module) => module.default))
}
const hasData = computed(() => ({
  gravity: props.batch.gravityCount > 0,
  pressure: props.batch.pressureCount > 0,
  temp: props.batch.temperatureCount > 0
}))
const measurementView = ref<MeasurementView>('gravity')
const visibleViews = computed(() =>
  measurementViews.filter((view) => view.value === 'gravity' || hasData.value[view.value] || view.value === measurementView.value)
)
const measurementComponent = computed(() => components[measurementView.value])

function isMeasurementView(value: unknown): value is MeasurementView {
  return measurementViews.some((view) => view.value === value)
}

function selectionFromQuery() {
  const query = router.currentRoute.value.query ?? {}
  if (typeof query.view === 'string') {
    measurementView.value = isMeasurementView(query.view) ? query.view : 'gravity'
  } else if (isMeasurementView(query.tab)) {
    measurementView.value = query.tab
  } else {
    measurementView.value = measurementViews.find((view) => hasData.value[view.value])?.value ?? 'gravity'
  }
}

watch(
  () => [props.batch.id, router.currentRoute.value.query?.view, router.currentRoute.value.query?.tab],
  selectionFromQuery,
  { immediate: true }
)

function selectMeasurementView(view: MeasurementView) {
  measurementView.value = view
  void router.replace({
    query: { ...(router.currentRoute.value.query ?? {}), tab: 'measurements', view }
  })
}
</script>

<style scoped>
.measurement-data-dot {
  display: inline-block;
  width: 0.35rem;
  height: 0.35rem;
  border-radius: 50%;
  background: currentColor;
}
</style>
