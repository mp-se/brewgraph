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
  Brewfather batch link/import, extracted from BatchView.vue (structural
  refactor, no behavior change). Owns fetching the Brewfather batch list and
  the picker modal; the caller decides what to do with the matched batch, the
  same shape as BatchBeerXmlImportFragment's `@imported` event.
-->
<template>
  <span>
    <app-button
      type="button"
      variant="outline-secondary" class="app-width-2"
      :disabled="global.disabled || brewfatherLoading || brewfatherOptions.length <= 1"
      @click="openBrewfatherModal"
    >Brewfather</app-button>

    <AppSelectDialog
      id="brewfather-import-trigger"
      title="Brewfather"
      message="Select a Brewfather batch to import"
      :options="brewfatherOptions"
      :callback="brewfatherModalCallback"
      :disabled="global.disabled"
    />
  </span>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { global, brewfatherStore } from '@/modules/pinia'
import { logDebug } from '@/ui'

const emit = defineEmits(['linked', 'cleared'])

const brewfatherOptions = ref([{ label: '- Not connected -', value: '' }])
const brewfatherLoading = ref(false)

function openBrewfatherModal() {
  document.getElementById('brewfather-import-trigger')?.click()
}

function brewfatherModalCallback(ok, id) {
  if (!ok) return
  if (id) {
    const match = brewfatherStore.batches.find((b) => b.brewfatherId === id)
    if (match) emit('linked', match)
  } else {
    emit('cleared')
  }
}

async function loadBrewfatherOptions() {
  brewfatherLoading.value = true
  const success = await brewfatherStore.getBatchList()
  logDebug('BatchBrewfatherLinkFragment.loadBrewfatherOptions()', success)

  if (success) {
    brewfatherOptions.value = [{ label: '- Not connected -', value: '' }]
    brewfatherStore.batches.forEach((b) => {
      brewfatherOptions.value.push({
        label: b.name + ', ' + b.brewDate + ', ' + b.brewer + ', ' + b.style,
        value: b.brewfatherId
      })
    })
  }

  brewfatherLoading.value = false
}

onMounted(() => {
  void loadBrewfatherOptions()
})
</script>
