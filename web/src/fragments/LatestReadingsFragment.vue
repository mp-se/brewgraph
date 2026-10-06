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
  <div class="col-md-4" v-if="readings && readings.length > 0">
    <AppCard :header="title" title="">
      <q-markup-table class="app-table app-table--dense app-table--striped q-mb-none">
        <thead>
          <tr>
            <th>Time</th>
            <slot name="headers"></slot>
          </tr>
        </thead>
        <tbody>
          <tr v-for="reading in readings" :key="reading.id || reading.createdAt">
            <td>{{ formatTime(reading.createdAt) }}</td>
            <slot name="row" :reading="reading"></slot>
          </tr>
        </tbody>
      </q-markup-table>
    </AppCard>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: 'Latest Readings'
  },
  readings: {
    type: Array,
    default: () => []
  }
})

function formatTime(ts) {
  if (!ts) return ''
  return ts.substring(0, 16).replace('T', ' ')
}
</script>
