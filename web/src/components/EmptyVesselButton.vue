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
  <app-button
    v-if="canEmpty"
    type="button"
    variant="negative"
    class="app-width-2"
    data-testid="empty-vessel"
    :disabled="disabled || isSaving"
    @click="openConfirm"
  >
    <q-icon name="logout" /> Empty
  </app-button>

  <q-dialog v-model="confirmOpen" persistent>
    <q-card class="app-dialog-card">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6">Empty {{ vessel.name || 'vessel' }}</div>
      </q-card-section>
      <q-card-section data-testid="empty-vessel-message">
        <span v-if="vessel.batchId">This ends the link to batch "{{ batchLabel }}". </span>
        <span v-if="vessel.tapId">It is released from tap "{{ tapLabel }}". </span>
        <span>The vessel is marked clean with nothing remaining. The vessel itself is kept.</span>
      </q-card-section>
      <q-card-actions align="right" class="app-dialog-actions">
        <q-btn flat no-caps label="Cancel" data-testid="empty-vessel-cancel" :disabled="isSaving" @click="confirmOpen = false" />
        <q-btn
          no-caps
          color="negative"
          label="Empty"
          data-testid="empty-vessel-confirm"
          :disabled="isSaving"
          :loading="isSaving"
          @click="empty"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { global, tapStore, vesselStore } from '@/modules/pinia'
import type { StorageVessel } from '@/modules/classes'

const props = defineProps<{ vessel: StorageVessel; disabled?: boolean }>()
const emit = defineEmits<{ emptied: [vessel: StorageVessel] }>()

const confirmOpen = ref(false)
const isSaving = ref(false)

// Clean with nothing remaining and no batch or tap link: there is nothing left to empty.
const canEmpty = computed(() => {
  const v = props.vessel
  const nothingRemaining = (v.volumeRemaining ?? 0) <= 0 && (v.bottlesRemaining ?? 0) <= 0
  return !(v.status === 'clean' && nothingRemaining && !v.batchId && !v.tapId)
})

const batchLabel = computed(() => props.vessel.batchName || 'linked batch')
const tapLabel = computed(
  () => tapStore.tapList.find((t) => t.id === props.vessel.tapId)?.name || 'assigned tap'
)

// The tap list is not loaded on every page, so fetch it when the dialog needs a tap's name.
async function openConfirm() {
  confirmOpen.value = true
  if (props.vessel.tapId && !tapStore.tapList.some((t) => t.id === props.vessel.tapId)) {
    await tapStore.getTapList()
  }
}

// Sends only batch_id: null; the server detaches the batch and tap, marks the vessel clean
// and zeroes the remaining volume and bottles.
async function empty() {
  global.clearMessages()
  isSaving.value = true
  try {
    const result = await vesselStore.assignBatch(props.vessel.id, null)
    if (result) {
      confirmOpen.value = false
      emit('emptied', result)
    } else {
      global.messageError = 'Failed to empty vessel'
    }
  } finally {
    isSaving.value = false
  }
}

defineExpose({ confirmOpen, canEmpty, empty, openConfirm })
</script>
