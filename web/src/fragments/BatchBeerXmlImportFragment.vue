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
  <span>
    <app-button
      type="button"
      variant="outline-secondary" class="app-width-2"
      :disabled="global.disabled"
      @click="triggerImport"
    >
      BeerXML
    </app-button>
    <input
      ref="fileInput"
      type="file"
      accept=".xml,.beerxml"
      style="display: none"
      @change="onFile"
    />
  </span>
</template>

<script setup>
import { ref } from 'vue'
import { global } from '@/modules/pinia'
import { parseBeerXml } from '@brewgraph/core'
import { logDebug } from '@/ui'

const emit = defineEmits(['imported'])

const fileInput = ref(null)

function triggerImport() {
  fileInput.value?.click()
}

async function onFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    const xml = await file.text()
    const imported = parseBeerXml(xml)
    if (!imported) {
      global.messageError = 'Could not parse BeerXML file'
      return
    }
    emit('imported', imported)
    global.messageSuccess = `Imported "${imported.name || 'recipe'}" from BeerXML`
  } catch (e) {
    logDebug('BeerXML import error', e)
    global.messageError = 'Failed to read BeerXML file'
  }
  event.target.value = ''
}
</script>
