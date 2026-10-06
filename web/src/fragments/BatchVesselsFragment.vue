<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<template>
  <div class="row q-col-gutter-md">
    <!-- Kegs -->
    <div class="col-12" data-testid="batch-kegs">
      <div class="row items-center q-gutter-sm q-mb-sm">
        <label class="text-weight-bold">Kegs</label>
        <div class="row q-gutter-xs no-wrap">
          <q-btn
            dense no-caps outline color="secondary" icon="link"
            :disabled="disabled || !emptyKegsLoaded || emptyKegs.length === 0"
            @click="openAssignKegModal"
            label="Assign"
          />
          <q-btn
            dense no-caps outline color="primary" icon="add_circle"
            :disabled="disabled"
            @click="openAddKegModal"
            label="Add"
          />
        </div>
      </div>
      <q-markup-table v-if="batchKegs.length > 0" dense separator="horizontal" class="app-table app-table--striped">
        <thead>
          <tr><th>Name</th><th>Status</th><th>Volume</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="v in batchKegs" :key="v.id">
            <td>{{ v.name }}</td>
            <td>{{ v.status }}</td>
            <td>{{ vesselAmount(v) }}</td>
            <td>
              <div class="row q-gutter-xs no-wrap">
              <router-link :to="{ name: 'vessel', params: { id: v.id } }">
                <q-btn dense no-caps color="primary" icon="edit" aria-label="Edit vessel" />
              </router-link>
              <q-btn
                dense no-caps outline color="negative" icon="logout"
                :disabled="disabled"
                title="Empty keg"
                aria-label="Empty keg"
                @click="emptyKeg(v)"
                label="Empty"
              />
              </div>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
      <p v-else class="text-grey-7">No kegs assigned to this batch.</p>
    </div>

    <!-- Bottles -->
    <div class="col-12 q-mt-md" data-testid="batch-bottles">
      <div class="row items-center q-gutter-sm q-mb-sm">
        <label class="text-weight-bold">Bottles</label>
        <q-btn
          dense no-caps outline color="primary" icon="add_circle"
          :disabled="disabled"
          @click="openAddBottlesModal"
          label="Add"
        />
      </div>
      <q-markup-table v-if="batchBottles.length > 0" dense separator="horizontal" class="app-table app-table--striped">
        <thead>
          <tr><th>Name</th><th>Count</th><th>Vol/btl</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="v in batchBottles" :key="v.id">
            <td>{{ v.name }}</td>
            <td>{{ v.bottlesRemaining }} / {{ v.bottleCount }}</td>
            <td>{{ v.bottleVolume }} L</td>
            <td><div class="row q-gutter-xs no-wrap">
              <router-link :to="{ name: 'vessel', params: { id: v.id } }">
                <q-btn dense no-caps color="primary" icon="edit" aria-label="Edit vessel" />
              </router-link>
              <q-btn
                dense no-caps outline color="negative" icon="delete"
                :disabled="disabled"
                @click="deleteBottles(v)"
                aria-label="Remove vessel"
              />
              </div>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
      <p v-else class="text-grey-7">No bottle batches for this batch.</p>
    </div>

    <q-dialog v-model="assignKegDialog"><q-card class="app-dialog-card">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6">Assign Keg</div><q-space /><q-btn icon="close" flat round dense v-close-popup aria-label="Close" />
      </q-card-section>
      <q-card-section>
            <div v-if="emptyKegs.length === 0" class="text-grey-7">
              No empty kegs available. Choose to add one instead.
            </div>
            <AppSelect
              v-else
              v-model="selectedKegId"
              :options="emptyKegOptions"
              label="Select keg"
              help=""
            />
      </q-card-section>
      <q-card-actions align="right" class="app-dialog-actions">
            <q-btn flat no-caps label="Cancel" v-close-popup />
            <q-btn
              no-caps color="primary" label="Assign"
              :disabled="!selectedKegId"
              @click="assignKeg"
            />
      </q-card-actions>
    </q-card></q-dialog>

    <!-- Add Keg modal -->
    <q-dialog v-model="addKegDialog"><q-card class="app-dialog-card">
      <q-card-section class="row items-center q-pb-none"><div class="text-h6">Add Keg</div><q-space /><q-btn icon="close" flat round dense v-close-popup aria-label="Close" /></q-card-section>
      <q-card-section><div class="row q-col-gutter-sm">
              <div class="col-12">
                <AppTextInput v-model="newKeg.name" label="Name" help="" required />
              </div>
              <div class="col-6">
                <AppInputNumber v-model="newKeg.totalVolume" label="Total volume" unit="L" min="0" max="1000" :step="stepFor('volume')" help="" />
              </div>
              <div class="col-6">
                <AppInputDate v-model="newKeg.fillDate" label="Fill date" />
              </div>
            </div>
      </q-card-section>
      <q-card-actions align="right" class="app-dialog-actions">
            <q-btn flat no-caps label="Cancel" v-close-popup />
            <q-btn
              no-caps color="primary" icon="add_circle" label="Add Keg"
              :disabled="!newKeg.name.trim()"
              @click="addKeg"
            />
      </q-card-actions>
    </q-card></q-dialog>

    <!-- Add Bottles modal -->
    <q-dialog v-model="addBottlesDialog"><q-card class="app-dialog-card">
      <q-card-section class="row items-center q-pb-none"><div class="text-h6">Add Bottles</div><q-space /><q-btn icon="close" flat round dense v-close-popup aria-label="Close" /></q-card-section>
      <q-card-section><div class="row q-col-gutter-sm">
              <div class="col-12">
                <AppTextInput v-model="newBottles.name" label="Name" help="" required />
              </div>
              <div class="col-6">
                <AppInputNumber v-model="newBottles.bottleCount" label="Bottle count" unit="btl" min="0" max="9999" step="1" help="" />
              </div>
              <div class="col-6">
                <AppInputNumber v-model="newBottles.bottleVolume" label="Volume per bottle" unit="L" min="0" max="10" :step="stepFor('volume')" help="" />
              </div>
              <div class="col-6">
                <AppInputDate v-model="newBottles.fillDate" label="Fill date" />
              </div>
            </div>
      </q-card-section>
      <q-card-actions align="right" class="app-dialog-actions">
            <q-btn flat no-caps label="Cancel" v-close-popup />
            <q-btn
              no-caps color="primary" icon="add_circle" label="Add Bottles"
              :disabled="!newBottles.name.trim()"
              @click="addBottles"
            />
      </q-card-actions>
    </q-card></q-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { global, vesselStore } from '@/modules/pinia'
import { StorageVessel, VESSEL_TYPE_BOTTLE, VESSEL_TYPE_KEG } from '@/modules/classes'
import type { PiniaModel } from '@/modules/piniaModel'
import { stepFor } from '@/modules/useUnitConversion'

const props = defineProps<{ batchId: string; readOnly?: boolean }>()
const disabled = computed(() => global.disabled || !!props.readOnly)

/*
 * Filling a vessel packages the batch server-side (status -> packaged, package date
 * stamped, measured OG/FG snapshotted). The batch form is rendered by the parent, so
 * without this it would keep showing "fermenting" and an empty package date until the
 * page was reloaded.
 */
const emit = defineEmits<{ 'batch-packaged': [] }>()

const batchKegs = computed(() =>
  vesselStore.vesselList.filter((v) => v.batchId === props.batchId && v.vesselType === VESSEL_TYPE_KEG)
)
const batchBottles = computed(() =>
  vesselStore.vesselList.filter((v) => v.batchId === props.batchId && v.vesselType === VESSEL_TYPE_BOTTLE)
)

function vesselAmount(v) {
  if (v.vesselType === VESSEL_TYPE_BOTTLE) {
    return v.bottlesRemaining != null ? `${v.bottlesRemaining} / ${v.bottleCount} bottles` : '—'
  }
  return `${Number(v.volumeRemaining).toFixed(1)} / ${Number(v.totalVolume).toFixed(1)} L`
}

const emptyKegs = ref<StorageVessel[]>([])
const emptyKegsLoaded = ref(false)
const selectedKegId = ref('')
const emptyKegOptions = computed(() =>
  emptyKegs.value.map((k) => ({ value: k.id, label: k.name }))
)

const newKeg = ref({ name: '', totalVolume: 20.0, fillDate: '' })
const newBottles = ref({ name: '', bottleCount: 0, bottleVolume: 0.33, fillDate: '' })

const assignKegDialog = ref(false)
const addKegDialog = ref(false)
const addBottlesDialog = ref(false)

async function openAssignKegModal() {
  selectedKegId.value = ''
  if (emptyKegs.value.length === 0) return
  assignKegDialog.value = true
}

async function loadEmptyKegs() {
  try {
    emptyKegs.value = (await vesselStore.listEmptyKegs()) ?? []
  } finally {
    emptyKegsLoaded.value = true
  }
}

onMounted(loadEmptyKegs)

function openAddKegModal() {
  newKeg.value = { name: '', totalVolume: 20.0, fillDate: '' }
  addKegDialog.value = true
}

function openAddBottlesModal() {
  newBottles.value = { name: '', bottleCount: 0, bottleVolume: 0.33, fillDate: '' }
  addBottlesDialog.value = true
}

async function assignKeg() {
  const keg = emptyKegs.value.find((k) => k.id === selectedKegId.value)
  if (!keg) return
  const result = await vesselStore.assignBatch(keg.id, props.batchId)
  if (result) {
    await vesselStore.getVesselList(props.batchId)
    emit('batch-packaged')
    assignKegDialog.value = false
  } else {
    global.messageError = 'Failed to assign keg'
  }
}

async function addKeg() {
  const name = newKeg.value.name.trim()
  if (!name) return
  const vessel = new StorageVessel({
    batchId: props.batchId,
    vesselType: VESSEL_TYPE_KEG,
    name,
    totalVolume: newKeg.value.totalVolume,
    volumeRemaining: newKeg.value.totalVolume,
    fillDate: newKeg.value.fillDate,
    status: 'filled',
  })
  const result = await vesselStore.addVessel(vessel)
  if (result) {
    await vesselStore.getVesselList(props.batchId)
    emit('batch-packaged')
    addKegDialog.value = false
  } else {
    global.messageError = 'Failed to add keg'
  }
}

async function addBottles() {
  const name = newBottles.value.name.trim()
  if (!name) return
  const count = newBottles.value.bottleCount
  const vessel = new StorageVessel({
    batchId: props.batchId,
    vesselType: VESSEL_TYPE_BOTTLE,
    name,
    bottleCount: count,
    bottlesRemaining: count,
    bottleVolume: newBottles.value.bottleVolume,
    totalVolume: count * newBottles.value.bottleVolume,
    volumeRemaining: count * newBottles.value.bottleVolume,
    fillDate: newBottles.value.fillDate,
    status: 'filled',
  })
  const result = await vesselStore.addVessel(vessel)
  if (result) {
    await vesselStore.getVesselList(props.batchId)
    emit('batch-packaged')
    addBottlesDialog.value = false
  } else {
    global.messageError = 'Failed to add bottle batch'
  }
}

// Empties the keg: detaches it from this batch and sets status to clean. The keg row
// survives -- its keg_identifier history feeds the hygiene reminder across refills.
// Not a delete, and not the same as releasing a still-full keg from its tap.
async function emptyKeg(v: PiniaModel<StorageVessel>) {
  const result = await vesselStore.assignBatch(v.id, null)
  if (result) {
    await vesselStore.getVesselList(props.batchId)
  } else {
    global.messageError = 'Failed to empty keg'
  }
}

async function deleteBottles(v: PiniaModel<StorageVessel>) {
  const ok = await vesselStore.deleteVessel(v.id)
  if (ok) {
    await vesselStore.getVesselList(props.batchId)
  } else {
    global.messageError = 'Failed to delete bottle batch'
  }
}
</script>
