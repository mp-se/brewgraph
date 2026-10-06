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
  <div class="app-page">
    <p></p>
    <p class="text-h6">Support</p>
    <hr />
    <p class="text-subtitle2">Log status</p>
    <pre>{{ JSON.stringify(logData, null, 2) }}</pre>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { apiFetch } from '@/modules/apiClient'
import { logDebug, logError } from '@/ui'

// The BLE scanner posts every format to ingest, so BLE devices are ordinary devices —
// last-seen and readings live on the device pages, with history this dump never had.
// There is no BLE panel or `ble` array here.
const logData = ref({})

onMounted(() => {
  logDebug('SupportView.onMounted()')

  apiFetch('GET', 'system/self-test')
    .then((res) => {
      return res.json()
    })
    .then((json) => {
      json.log.forEach((entry) => {
        const [, deviceid, attribute] = entry.name.split('_')
        if (!logData.value[deviceid]) logData.value[deviceid] = {}
        let value = entry.value
        if (attribute === 'start' || attribute === 'last') {
          // Convert to 'YYYY-MM-DD HH:mm' format (assume value is a Unix timestamp in seconds)
          const date = new Date(value * 1000)
          const pad = (n) => n.toString().padStart(2, '0')
          value = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
        }
        logData.value[deviceid][attribute] = value
      })

      logDebug('SupportView.onMounted()', json)
    })
    .catch((err) => {
      logError('SupportView.onMounted()', err)
    })
})
</script>
