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
  <div style="position: relative">
    <label class="app-field-label">Yeast</label>
    <input
      type="text"
      class="app-native-input"
      v-model="yeastQuery"
      :disabled="global.disabled"
      placeholder="Search yeast strains…"
      autocomplete="off"
      @focus="onYeastFocus"
      @blur="onYeastBlur"
      @input="onYeastInput"
    />
    <ul
      v-if="yeastDropdownOpen && yeastSuggestions.length"
      class="app-list-group shadow-1"
      style="position: absolute; z-index: 1000; width: 100%; max-height: 220px; overflow-y: auto"
    >
      <li
        v-for="s in yeastSuggestions"
        :key="s.id"
        class="app-list-group__item cursor-pointer q-py-xs"
        style="cursor: pointer; font-size: 0.85rem"
        @mousedown.prevent="selectYeast(s)"
      >
        <strong>{{ s.productId }}</strong> {{ s.name }}
        <small class="text-grey-7 q-ml-xs">{{ s.laboratory }}</small>
      </li>
    </ul>
    <div v-if="yeastProductId" class="app-field-help text-grey-7">
      ID: {{ yeastProductId }}
      <a href="#" class="q-ml-sm text-negative" @click.prevent="clearYeast">×&nbsp;clear</a>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { global, yeastStrainStore } from '@/modules/pinia'
import { logDebug } from '@/ui'

const yeast = defineModel('yeast', { type: String, default: '' })
const yeastProductId = defineModel('yeastProductId', { type: String, default: '' })

const yeastQuery = ref('')
const yeastDropdownOpen = ref(false)
const yeastSuggestions = ref([])

// Keep the query in sync when the batch's yeast changes externally
// (initial load, Brewfather sync, BeerXML import).
watch(yeast, (value) => { yeastQuery.value = value ?? '' }, { immediate: true })

function onYeastFocus() {
  logDebug('YeastSelector.onYeastFocus()', `query="${yeastQuery.value}" loaded=${yeastStrainStore.loaded} strains=${yeastStrainStore.strains.length}`)
  yeastSuggestions.value = yeastStrainStore.search(yeastQuery.value)
  logDebug('YeastSelector.onYeastFocus()', `suggestions=${yeastSuggestions.value.length}`)
  yeastDropdownOpen.value = true
}

function onYeastInput() {
  logDebug('YeastSelector.onYeastInput()', `query="${yeastQuery.value}"`)
  yeastSuggestions.value = yeastStrainStore.search(yeastQuery.value)
  yeastDropdownOpen.value = true
}

function onYeastBlur() {
  setTimeout(() => {
    yeastDropdownOpen.value = false
  }, 150)
  // Revert query if user typed without selecting from library
  yeastQuery.value = yeast.value
}

function selectYeast(strain) {
  yeast.value = strain.name
  yeastProductId.value = strain.productId
  yeastQuery.value = strain.name
  yeastDropdownOpen.value = false
}

function clearYeast() {
  yeast.value = ''
  yeastProductId.value = ''
  yeastQuery.value = ''
}

</script>
