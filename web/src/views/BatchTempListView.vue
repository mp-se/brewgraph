<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<template>
  <div class="app-page">
    <div class="row justify-between items-center q-mb-sm">
      <p class="text-h6 q-mb-none">Batch Temperature List - '{{ batchName }}'</p>
      <router-link :to="{ name: 'batch-list' }">
        <app-button type="button" variant="secondary" dense>
          <q-icon name="list" /> Batch list
        </app-button>
      </router-link>
    </div>
    <hr class="app-page-divider" />

    <q-markup-table v-if="readings.length" class="app-table app-table--striped">
      <thead>
        <tr>
          <th scope="col">Date</th>
          <th scope="col">Temperature (°{{ config.isTempC ? 'C' : 'F' }})</th>
          <th scope="col">Probe</th>
          <th scope="col">Battery</th>
          <th scope="col">RSSI</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="reading in readings" :key="reading.id">
          <td>{{ reading.createdAt.substring(0, 19).replace('T', ' ') }}</td>
          <td>{{ getFormattedTemperature(reading.temperature) }}</td>
          <td>{{ reading.tempType }}</td>
          <td>{{ reading.battery === null ? '--' : reading.battery.toFixed(2) }}</td>
          <td>{{ reading.rssi ?? '--' }}</td>
        </tr>
      </tbody>
    </q-markup-table>
    <div v-else-if="loaded" class="app-alert app-alert--info">No temperature readings found for this batch.</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { batchStore, config, global, tempReadingStore } from '@/modules/pinia'
import router from '@/modules/router'
import { getFormattedTemperature } from '@/modules/utils'
import type { TemperatureReading } from '@/modules/tempReadingStore'

const batchName = ref('')
const readings = ref<TemperatureReading[]>([])
const loaded = ref(false)

onMounted(async () => {
  const batchId = String(router.currentRoute.value.params.id ?? '')
  const batch = await batchStore.getBatch(batchId)
  if (batch) batchName.value = batch.name
  else global.messageError = 'Failed to load batch ' + batchId

  const data = await tempReadingStore.getTempListForBatch(batchId)
  if (data) readings.value = data
  loaded.value = true
})
</script>
