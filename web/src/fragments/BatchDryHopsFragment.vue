<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<template>
  <div class="row">
    <div class="col-md-12">
      <div class="row justify-between items-center q-mb-sm">
        <label class="app-field-label text-weight-bold q-mb-none">Dry Hops</label>
        <app-button
          type="button"
          variant="outline-primary" dense
          :disabled="disabled"
          @click="openAddModal"
        ><q-icon name="add_circle" /> Add</app-button>
      </div>

      <q-markup-table v-if="dryHops.length > 0" class="app-table app-table--dense app-table--striped">
        <thead>
          <tr>
            <th>Name</th>
            <th>Amount (g)</th>
            <th>Trigger</th>
            <th>Triggered</th>
            <th>Completed</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in dryHops" :key="h.id">
            <td>{{ h.name }}</td>
            <td>{{ h.amount }}</td>
            <td>{{ triggerLabel(h) }}</td>
            <td>{{ h.triggeredAt ? formatDate(h.triggeredAt) : '—' }}</td>
            <td>{{ h.completedAt ? formatDate(h.completedAt) : '—' }}</td>
            <td class="row q-gutter-xs">
              <app-button
                v-if="h.triggeredAt && !h.completedAt"
                type="button"
                variant="positive" dense
                :disabled="disabled"

                title="Mark completed"
                @click="completeDryHop(h.id)"
              ><q-icon name="check_circle" /></app-button>
              <app-button
                type="button"
                variant="outline-negative" dense
                :disabled="disabled"

                title="Delete"
                @click="deleteDryHop(h.id)"
              ><q-icon name="delete" /></app-button>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
      <p v-else class="text-grey-7">No dry hops scheduled.</p>
    </div>

    <q-dialog v-model="addDialog"><q-card class="app-dialog-card">
          <q-card-section class="row items-center q-pb-none"><div class="text-h6">Add Dry Hop</div><q-space /><q-btn icon="close" flat round dense v-close-popup aria-label="Close" /></q-card-section>
          <q-card-section>
            <div class="row q-col-gutter-sm">
              <div class="col-12">
                <AppTextInput v-model="newHop.name" label="Hop name" help="" required />
              </div>
              <div class="col-6">
                <AppInputNumber v-model="newHop.amount" label="Amount" unit="g" min="0" max="10000" step="1" help="" />
              </div>
              <div class="col-6">
                <label class="app-field-label">Trigger method</label>
                <select v-model="newHop.triggerMethod" class="app-native-input app-native-input--dense">
                  <option value="hours_before_completion">Hours before completion</option>
                  <option value="gravity_level">Gravity level</option>
                </select>
              </div>
              <div class="col-6" v-if="newHop.triggerMethod === 'hours_before_completion'">
                <AppInputNumber v-model="newHop.triggerHoursBefore" label="Hours before" unit="h" min="1" max="720" step="1" help="" />
              </div>
              <div class="col-6" v-if="newHop.triggerMethod === 'gravity_level'">
                <AppInputNumber v-model="newHop.triggerGravity" label="Trigger SG" unit="SG" min="0.990" max="1.200" :step="stepFor('gravity')" help="" />
              </div>
            </div>
          </q-card-section>
          <q-card-actions align="right" class="app-dialog-actions">
            <q-btn flat no-caps label="Cancel" v-close-popup />
            <q-btn
              no-caps color="primary" icon="add_circle" label="Add"
              :disabled="!newHop.name.trim()"
              @click="addDryHop"
            />
          </q-card-actions>
    </q-card></q-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { global } from '@/modules/pinia'
import { apiJson, apiOk } from '@/modules/apiClient'
import { logDebug } from '@/ui'
import { stepFor } from '@/modules/useUnitConversion'

const props = defineProps<{ batchId: string; readOnly?: boolean }>()
const disabled = computed(() => global.disabled || !!props.readOnly)

interface DryHop {
  id: string
  name: string
  amount: number
  triggerMethod: string
  triggerGravity: number | null
  triggerHoursBefore: number | null
  triggeredAt: string | null
  completedAt: string | null
}

const dryHops = ref<DryHop[]>([])

const newHop = ref({
  name: '',
  amount: 50,
  triggerMethod: 'hours_before_completion',
  triggerHoursBefore: 24,
  triggerGravity: null as number | null,
})

const addDialog = ref(false)

function triggerLabel(h: DryHop): string {
  if (h.triggerMethod === 'gravity_level' && h.triggerGravity != null) {
    return `SG ≤ ${h.triggerGravity.toFixed(3)}`
  }
  if (h.triggerHoursBefore != null) {
    return `${h.triggerHoursBefore}h before done`
  }
  return '—'
}

function formatDate(iso: string): string {
  return iso ? new Date(iso).toLocaleString() : '—'
}

async function loadDryHops() {
  logDebug('BatchDryHopsFragment.loadDryHops()')
  const batch = await apiJson<{ dryHops?: DryHop[] }>('GET', `batches/${props.batchId}`, undefined, { busy: false })
  dryHops.value = batch?.dryHops ?? []
}

function openAddModal() {
  newHop.value = { name: '', amount: 50, triggerMethod: 'hours_before_completion', triggerHoursBefore: 24, triggerGravity: null }
  addDialog.value = true
}

async function addDryHop() {
  const name = newHop.value.name.trim()
  if (!name) return
  const payload: Record<string, unknown>[] = [
    {
      name,
      amount: newHop.value.amount,
      triggerMethod: newHop.value.triggerMethod,
      triggerGravity: newHop.value.triggerMethod === 'gravity_level' ? newHop.value.triggerGravity : null,
      triggerHoursBefore: newHop.value.triggerMethod === 'hours_before_completion' ? newHop.value.triggerHoursBefore : null,
    }
  ]
  const ok = await apiOk('POST', `batches/${props.batchId}/dry-hops`, payload)
  if (ok) {
    await loadDryHops()
    addDialog.value = false
  } else {
    global.messageError = 'Failed to add dry hop'
  }
}

// Completion is a timestamp column, so it goes through the ordinary dry-hop PATCH.
// The client supplies the moment rather than the server stamping now(), which is what
// makes the reverse — clearing a hop marked done by mistake — possible at all.
async function completeDryHop(hopId: string) {
  const ok = await apiOk('PATCH', `batches/${props.batchId}/dry-hops/${hopId}`, {
    completedAt: new Date().toISOString()
  })
  if (ok) {
    await loadDryHops()
  } else {
    global.messageError = 'Failed to complete dry hop'
  }
}

async function deleteDryHop(hopId: string) {
  const ok = await apiOk('DELETE', `batches/${props.batchId}/dry-hops/${hopId}`, undefined)
  if (ok) {
    await loadDryHops()
  } else {
    global.messageError = 'Failed to delete dry hop'
  }
}

onMounted(async () => {
  await loadDryHops()
})
</script>
