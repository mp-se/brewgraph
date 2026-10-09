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
  <div v-if="steps && (steps.length > 0 || editable)">
    <div class="row justify-between items-center q-mb-sm">
      <label class="app-field-label text-weight-bold">Fermentation Steps</label>

      <div class="row q-gutter-xs">
        <app-button type="button" variant="outline-primary" dense @click="addStep()"><q-icon name="add_circle" /> Add</app-button>
      </div>
    </div>

    <q-markup-table class="app-table app-table--dense app-table--striped">
      <thead>
        <tr>
          <th class="col-md-1">#</th>
          <th class="col-md-3">Name</th>
          <th class="col-md-2">Type</th>
          <th class="col-md-2">Temp ({{ tempUnit }})</th>
          <th class="col-md-1">Days</th>
          <th class="col-md-2">Date</th>
          <th v-if="editable" class="col-md-1"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(step, index) in steps" :key="step.order ?? index">
          <td>{{ step.order ?? index + 1 }}</td>
          <td>
            <input v-if="editable" type="text" class="app-native-input app-native-input--dense" :value="step.name"
              @input="updateStep(index, 'name', $event.target.value)" />
            <span v-else>{{ step.name }}</span>
          </td>
          <td>
            <input v-if="editable" type="text" class="app-native-input app-native-input--dense" :value="step.type"
              @input="updateStep(index, 'type', $event.target.value)" />
            <span v-else>{{ step.type }}</span>
          </td>
          <td>
            <input v-if="editable" type="number" class="app-native-input app-native-input--dense" style="width: 80px"
              :value="displayTemperature(step.temp)" :step="stepFor('temperature')" @input="updateTemperature(index, Number($event.target.value))" />
            <span v-else>{{ displayTemperature(step.temp) }}</span>
          </td>
          <td>
            <input v-if="editable" type="number" class="app-native-input app-native-input--dense" style="width: 70px"
              :value="step.days" min="1" @input="updateStep(index, 'days', Number($event.target.value))" />
            <span v-else>{{ step.days }}</span>
          </td>
          <td>{{ step.date }}</td>
          <td v-if="editable">
            <app-button type="button" variant="negative" dense @click="removeStep(index)" aria-label="Clear active steps">
              <q-icon name="delete_forever" />
            </app-button>
          </td>
        </tr>
      </tbody>
    </q-markup-table>

    <p v-if="editable && steps.length === 0" class="text-grey-7 q-mb-none">No fermentation steps yet.</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { tempToC, tempToF, roundValue } from '@/modules/utils'
import { decimalsFor, stepFor } from '@/modules/useUnitConversion'

const props = defineProps({
  fermentationSteps: {
    type: Array,
    default: () => []
  },
  tempUnit: {
    type: String,
    default: 'C'
  },
  editable: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:fermentationSteps'])

const editable = computed(() => {
  return props.editable
})

const steps = computed(() => props.fermentationSteps ?? [])

function updateStep(index, field, value) {
  const updated = steps.value.map((s, i) => (i === index ? { ...s, [field]: value } : s))
  emit('update:fermentationSteps', updated)
}

function displayTemperature(temp) {
  return roundValue(props.tempUnit === 'F' ? tempToF(temp) : temp, decimalsFor('temperature'))
}

function updateTemperature(index, displayedTemp) {
  updateStep(index, 'temp', props.tempUnit === 'F' ? tempToC(displayedTemp) : displayedTemp)
}

function removeStep(index) {
  const updated = steps.value.filter((_, i) => i !== index)
  emit('update:fermentationSteps', updated)
}

function addStep() {
  const nextOrder = steps.value.length
  const updated = [
    ...steps.value,
    {
      order: nextOrder,
      name: `Step ${nextOrder + 1}`,
      type: '',
      temp: 20,
      days: 1,
      date: null
    }
  ]
  emit('update:fermentationSteps', updated)
}
</script>
