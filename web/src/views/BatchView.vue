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
    <AppPageHeader title="Batch" />

    <template v-if="batch != null">
      <div class="row q-col-gutter-lg batch-editor-layout">
      <div :class="!isNew() ? 'col-md-9 batch-editor-layout__main' : 'col-md-12 batch-editor-layout__main'">
      <form
        ref="batchForm"
        @submit.prevent="save"
        class="app-validation legacy-batch-form"
        :class="{ 'was-validated': showValidation }"
        novalidate
      >
        <div class="row q-col-gutter-md batch-editor-form-grid">
          <BatchDetailsFormFragment
            v-model:batch="batch"
            :gravity-device-options="gravityDeviceOptions"
            :pressure-device-options="pressureDeviceOptions"
            :temp-control-device-options="tempControlDeviceOptions"
            :gravity-device="gravityDevice"
            :pressure-device="pressureDevice"
            :chamber-device="chamberDevice"
            :show-controller-active="showControllerActive"
            :is-archived="isArchived"
          />

          <div class="col-md-12 batch-editor-section-divider">
            <hr />
          </div>

          <div class="col-md-12">

            <FermentationStep
              v-model:fermentationSteps="parsedFermentationSteps"
              :tempUnit="config.tempUnit"
              :editable="!isArchived"
            >
            </FermentationStep>
          </div>

          <template v-if="!isNew()">
            <div class="col-md-12 batch-editor-section-divider">
              <hr />
            </div>
            <div class="col-md-12">
              <BatchDryHopsFragment :batch-id="batch.id" :read-only="isArchived" />
            </div>
            <div class="col-md-12 batch-editor-section-divider">
              <hr />
            </div>
            <div class="col-md-12">
              <BatchVesselsFragment :batch-id="batch.id" :read-only="isArchived" @batch-packaged="reloadBatchStatus" />
            </div>
          </template>

        </div>

        <BatchEditorActions
          :disabled="global.disabled"
          :saving="isSaving"
          :has-changes="batchChanged()"
          :batch-name="batch.name"
          :is-new="isNew()"
          :is-archived="isArchived"
          :can-fermentation-control="Boolean(batch.chamberDeviceId && batch.fermentationSteps != '')"
          :fermentation-control-disabled="global.batchChanged"
          :batch-id="router.currentRoute.value.params.id"
          @export="exportBatchJson"
          @archive="archiveBatch"
          @unarchive="unarchiveBatch"
          @imported="applyBeerXmlImport"
          @linked="applyBrewfatherLink"
          @cleared="clearBrewfatherLink"
        />
      </form>

      <div class="row q-col-gutter-sm q-mt-sm" v-if="gravityDevice">
        <DeviceSetupFragment
          :device-type="gravityDevice.deviceType"
          :token="gravityDevice.token"
          :has-readings="!!gravityDevice.lastSeen"
        />
      </div>
      <div class="row q-col-gutter-sm q-mt-sm" v-if="pressureDevice">
        <DeviceSetupFragment
          :device-type="pressureDevice.deviceType"
          :token="pressureDevice.token"
          :has-readings="!!pressureDevice.lastSeen"
        />
      </div>
      <div class="row q-col-gutter-sm q-mt-sm" v-if="chamberDevice">
        <DeviceSetupFragment
          :device-type="chamberDevice.deviceType"
          :token="chamberDevice.token"
          :has-readings="!!chamberDevice.lastSeen"
        />
      </div>
      </div><!-- /col-form -->

      <!-- Notes sidebar -->
      <div v-if="!isNew()" class="col-md-3 app-border-left batch-editor-layout__notes">
        <BatchNotesFragment :batch-id="batch.id" :read-only="isArchived" />
      </div>
      </div><!-- /row -->
    </template>

    <template v-else>
      <div class="row q-col-gutter-sm">
        <div class="col-md-12">
          <p class="text-subtitle1">Loading...</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, watch, computed } from 'vue'
import {
  global,
  deviceStore,
  batchStore,
  batchNoteStore,
  config
} from '@/modules/pinia'
import { storeToRefs } from 'pinia'
import { download } from '@/modules/utils'
import { buildExportDocument } from '@/modules/backup/exportDocument'
import { Batch } from '@/modules/classes'
import router from '@/modules/router'
import { logDebug } from '@/ui'
import AppPageHeader from '@/components/AppPageHeader.vue'
import FermentationStep from '@/fragments/FermentationStepFragment.vue'
import BatchNotesFragment from '@/fragments/BatchNotesFragment.vue'
import DeviceSetupFragment from '@/fragments/DeviceSetupFragment.vue'
import BatchVesselsFragment from '@/fragments/BatchVesselsFragment.vue'
import BatchDryHopsFragment from '@/fragments/BatchDryHopsFragment.vue'
import BatchDetailsFormFragment from '@/fragments/BatchDetailsFormFragment.vue'
import BatchEditorActions from '@/components/BatchEditorActions.vue'
import { useDeviceOptions } from '@/modules/useDeviceOptions'
import {
  parseFermentationStepsForEditor,
  serializeFermentationSteps,
  persistFermentationSteps as persistSteps,
  hasActiveFermentationStepNow
} from '@/modules/fermentationStepEditor'
import { persistDryHops } from '@/modules/dryHopEditor'

const batch = ref(null)
const batchSaved = ref(null)
const showValidation = ref(false)
const isSaving = ref(false)
const batchForm = ref(null)

/**
 * Validate this editor only. The generic validator walks every form
 * in the document, which makes the required fields in closed Keg, Bottles and
 * Dry Hop modals prevent an otherwise valid batch from being saved.
 */
function validateBatchForm() {
  const form = batchForm.value
  if (!form) return true

  const invalidControls = Array.from(form.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea'))
    .filter((control) => !control.disabled)
    .filter((control) => {
      const modal = control.closest('.modal')
      return !modal || modal.classList.contains('show')
    })
    .filter((control) => !control.checkValidity())

  form.classList.add('was-validated')
  if (invalidControls.length === 0) return true

  logDebug('BatchView.validateBatchForm()', 'BLOCKED: batch form is invalid', invalidControls.map((el) => ({ name: el.name, id: el.id, value: el.value, type: el.type, step: el.step, min: el.min, max: el.max })))
  return false
}

/*
 * Re-read the batch after a vessel is filled from it.
 *
 * Packaging is a server-side consequence of the vessel link, not something this view
 * asked for, so the fields it changes — status, package date, measured OG/FG — are
 * only knowable by asking. Replaces the old `packaged` event from the package modal,
 * which could hand them over directly because it made the change itself.
 */
async function reloadBatchStatus() {
  if (!batch.value) return
  const updated = await batchStore.getBatch(batch.value.id)
  if (!updated) return
  for (const field of ['status', 'packageDate', 'ogMeasured', 'fgMeasured']) {
    batch.value[field] = updated[field]
    // Move the saved baseline too. These values came *from* the server, so they are
    // already persisted; without this the form compares against a stale baseline and
    // shows "Save needed" for an edit the user never made.
    if (batchSaved.value) batchSaved.value[field] = updated[field]
  }
}

const isArchived = computed(() => batch.value?.status === 'archived')

/*
 * Reversible from either fermenting or packaged (server-enforced; see
 * docs/spec-api-batches.md "Archiving"). Both status and the saved baseline are updated
 * from the response so the form immediately reflects the read-only state without a
 * reload, matching reloadBatchStatus()'s baseline-sync pattern above.
 */
async function archiveBatch() {
  logDebug('BatchView.archiveBatch()', batch.value?.id)
  if (!batch.value) return
  const updated = await batchStore.archiveBatch(batch.value.id)
  if (updated) {
    batch.value.status = updated.status
    if (batchSaved.value) batchSaved.value.status = updated.status
    global.messageSuccess = 'Batch archived'
  } else {
    global.messageError = 'Failed to archive batch'
  }
}

async function unarchiveBatch() {
  logDebug('BatchView.unarchiveBatch()', batch.value?.id)
  if (!batch.value) return
  const updated = await batchStore.unarchiveBatch(batch.value.id)
  if (updated) {
    batch.value.status = updated.status
    if (batchSaved.value) batchSaved.value.status = updated.status
    global.messageSuccess = 'Batch un-archived'
  } else {
    global.messageError = 'Failed to un-archive batch'
  }
}

function applyBeerXmlImport(imported) {
  if (!batch.value) return
  if (imported.name)              batch.value.name              = imported.name
  if (imported.style)             batch.value.style             = imported.style
  if (imported.brewer)            batch.value.brewer            = imported.brewer
  if (imported.og)                batch.value.og                = imported.og
  if (imported.fg)                batch.value.fg                = imported.fg
  if (imported.ibu  != null)      batch.value.ibu               = Math.round(imported.ibu)
  if (imported.ebc  != null)      batch.value.ebc               = Math.round(imported.ebc)
  if (imported.volume != null)    batch.value.volume            = imported.volume
  if (imported.carbonation != null) batch.value.carbonationVolumes = imported.carbonation
  if (imported.notes)             batch.value.notes             = imported.notes
  if (imported.yeast)             batch.value.yeast             = imported.yeast
  if (imported.fermentationSteps?.length) {
    parsedFermentationSteps.value = imported.fermentationSteps
  }
  if (imported.dryHops?.length) {
    stagedDryHops.value = imported.dryHops
  }
}

const {
  gravityDeviceOptions,
  pressureDeviceOptions,
  tempControlDeviceOptions,
  updateDeviceOptions
} = useDeviceOptions()

const activeFermentationSteps = ref([])

const gravityDevice = computed(() =>
  batch.value?.gravityDeviceId
    ? deviceStore.devices.find((d) => d.id === batch.value.gravityDeviceId) ?? null
    : null
)
const pressureDevice = computed(() =>
  batch.value?.pressureDeviceId
    ? deviceStore.devices.find((d) => d.id === batch.value.pressureDeviceId) ?? null
    : null
)
const chamberDevice = computed(() =>
  batch.value?.chamberDeviceId
    ? deviceStore.devices.find((d) => d.id === batch.value.chamberDeviceId) ?? null
    : null
)


const parsedFermentationSteps = ref([])
const stagedDryHops = ref([])

const showControllerActive = computed(() => {
  return (
    Boolean(batch.value?.chamberDeviceId) &&
    hasActiveFermentationStepNow(activeFermentationSteps.value)
  )
})

// Sync parsed steps back to batch whenever the fragment updates the array
// Convert F→C before storing (database always stores in Celsius)
watch(
  parsedFermentationSteps,
  (steps) => {
    if (batch.value) {
      batch.value.fermentationSteps = serializeFermentationSteps(steps)
    }
  },
  { deep: true }
)
function batchChanged() {
  logDebug('BatchView.batchChanged()')

  if (batch.value == null || batchSaved.value == null) {
    global.batchChanged = false
    return false
  }

  global.batchChanged = !Batch.compare(batch.value, batchSaved.value)
  return global.batchChanged
}

function isNew() {
  return router.currentRoute.value.params.id == 'new' ? true : false
}

/**
 * Download this batch as a `brewgraph-batch-export-v1` document.
 *
 * Assembled client-side from the ordinary REST responses; see
 * `modules/backup/exportDocument.ts`. The container is a list even for a single
 * batch, so the same reader handles this file and a whole-dataset backup.
 */
async function exportBatchJson() {
  logDebug('BatchView.exportBatchJson()', batch.value?.id)

  const id = batch.value?.id
  if (!id) return

  const releaseBusy = global.acquireBusy()
  try {
    // Refetch rather than exporting the in-memory batch: the view holds an
    // edited copy that may not have been saved, and an export must record what
    // is stored, not what is on screen.
    const stored = await batchStore.getBatch(id)
    if (!stored) {
      global.messageError = 'Failed to fetch batch with id ' + id
      return
    }
    const doc = buildExportDocument({
      batches: [stored],
      devices: deviceStore.deviceList ?? []
    })
    const safeName = (stored.name || 'batch').replace(/[^a-zA-Z0-9-_]+/g, '_')
    download(JSON.stringify(doc, null, 2), 'application/json', `brewgraph_${safeName}.json`)
  } finally {
    releaseBusy()
  }
}

const { updatedBatchData } = storeToRefs(global)
watch(updatedBatchData, async () => {
  if (!batch.value?.id || isNew() || isSaving.value) return
  const updated = batchStore.batchList.find((b) => b.id === batch.value.id)
  if (updated) batch.value = updated
  const storedSteps = (await deviceStore.getFermentationSteps(batch.value.id)) ?? []
  parsedFermentationSteps.value = parseFermentationStepsForEditor(storedSteps)
  batch.value.fermentationSteps = serializeFermentationSteps(parsedFermentationSteps.value)
  if (batchSaved.value) {
    batchSaved.value.fermentationSteps = batch.value.fermentationSteps
  }
  if (storedSteps.length > 0) activeFermentationSteps.value = storedSteps
})

function applyBrewfatherLink(b) {
  logDebug('BatchView.applyBrewfatherLink()', b?.brewfatherId)
  if (!batch.value) return

  batch.value.brewfatherBatchId = b.brewfatherId
  batch.value.name = b.name
  batch.value.brewDate = b.brewDate
  batch.value.brewer = b.brewer
  batch.value.style = b.style
  batch.value.ebc = b.ebc != null ? Math.round(b.ebc) : b.ebc
  batch.value.abv = b.abv
  batch.value.ibu = b.ibu != null ? Math.round(b.ibu) : b.ibu
  batch.value.og = b.og
  batch.value.fg = b.fg
  batch.value.carbonationVolumes = b.carbonation
  batch.value.volume = b.volume || null
  if (b.yeastName) batch.value.yeast = b.yeastName
  if (b.yeastProductId) batch.value.yeastProductId = b.yeastProductId
  // API delivers steps as a typed array; the watcher serializes the parsed
  // rows back onto batch.fermentationSteps (stored as a JSON string)
  parsedFermentationSteps.value = parseFermentationStepsForEditor(b.fermentationSteps)
  batch.value.fermentationSteps = serializeFermentationSteps(parsedFermentationSteps.value)
  if (b.dryHops?.length) {
    stagedDryHops.value = b.dryHops.map((h) => ({
      name: h.name,
      amount: h.amount,
      triggerHoursBefore: h.triggerHoursBefore
    }))
  }
}

function clearBrewfatherLink() {
  if (batch.value) batch.value.brewfatherBatchId = ''
}

onMounted(async () => {
  logDebug('BatchView.onMounted()')

  batch.value = null
  showValidation.value = true
  updateDeviceOptions()
  activeFermentationSteps.value = []

  if (isNew()) {
    batchSaved.value = new Batch()
    batch.value = new Batch()
    parsedFermentationSteps.value = []
  } else {
    const id = router.currentRoute.value.params.id
    const fromStore = batchStore.batchList.find((b) => b.id === id)
    const [batchResult, storedSteps] = await Promise.all([
      fromStore ? Promise.resolve(fromStore) : batchStore.getBatch(id),
      deviceStore.getFermentationSteps(id),
      batchNoteStore.getNotes(id),
    ])
    if (batchResult) {
      if (!fromStore) {
        for (const device of deviceStore.devices) {
          if (device.batchId !== batchResult.id) continue
          if (device.batchRole === 'gravity') batchResult.gravityDeviceId = device.id
          else if (device.batchRole === 'pressure') batchResult.pressureDeviceId = device.id
          else if (device.batchRole === 'chamber') batchResult.chamberDeviceId = device.id
        }
      }
      batch.value = batchResult
      parsedFermentationSteps.value = parseFermentationStepsForEditor(storedSteps ?? [])
      batch.value.fermentationSteps = serializeFermentationSteps(parsedFermentationSteps.value)

      batchSaved.value = Batch.fromJson(batchResult.toJson())
      batchSaved.value.fermentationSteps = batch.value.fermentationSteps
      batchSaved.value.gravityDeviceId = batch.value.gravityDeviceId
      batchSaved.value.pressureDeviceId = batch.value.pressureDeviceId
      batchSaved.value.chamberDeviceId = batch.value.chamberDeviceId

      if (storedSteps.length > 0) {
        activeFermentationSteps.value = storedSteps
      }
    } else {
      global.messageError = 'Failed to load batch ' + router.currentRoute.value.params.id
    }
  }

})

async function syncDeviceAssignments(batchId) {
  const roles = [
    {
      role: 'gravity',
      newId: batch.value?.gravityDeviceId,
      oldId: batchSaved.value?.gravityDeviceId
    },
    {
      role: 'pressure',
      newId: batch.value?.pressureDeviceId,
      oldId: batchSaved.value?.pressureDeviceId
    },
    {
      role: 'chamber',
      newId: batch.value?.chamberDeviceId,
      oldId: batchSaved.value?.chamberDeviceId
    }
  ]
  for (const { role, newId, oldId } of roles) {
    if (newId === oldId) continue
    if (oldId) {
      const oldDev = deviceStore.devices.find((d) => d.id === oldId)
      if (oldDev) {
        oldDev.batchId = null
        oldDev.batchRole = null
        await deviceStore.updateDevice(oldDev)
      }
    }
    if (newId) {
      const newDev = deviceStore.devices.find((d) => d.id === newId)
      if (newDev) {
        newDev.batchId = batchId
        newDev.batchRole = role
        await deviceStore.updateDevice(newDev)
      }
    }
  }
}

const save = async () => {
  logDebug('BatchView.save()')

  if (!validateBatchForm()) return

  logDebug('BatchView.save()', 'parsedFermentationSteps', JSON.stringify(parsedFermentationSteps.value))
  global.clearMessages()
  isSaving.value = true

  try {
    if (isNew()) {
      const result = await batchStore.addBatch(batch.value)
      logDebug('BatchView.addBatch()', result)
      if (result) {
        batch.value = result
        await syncDeviceAssignments(batch.value.id)
        const stepsSaved = await persistSteps(batch.value.id, parsedFermentationSteps.value)
        if (!stepsSaved) {
          global.messageError = 'Batch created, but failed to save fermentation steps'
          return
        }
        if (stagedDryHops.value.length > 0) {
          const dryHopsSaved = await persistDryHops(batch.value.id, stagedDryHops.value)
          if (!dryHopsSaved) {
            global.messageError = 'Batch created, but failed to save dry hops'
            return
          }
          stagedDryHops.value = []
        }
        batch.value.fermentationSteps = serializeFermentationSteps(parsedFermentationSteps.value)
        batchSaved.value = Batch.fromJson(batch.value.toJson())
        batchSaved.value.fermentationSteps = batch.value.fermentationSteps
        batchSaved.value.gravityDeviceId = batch.value.gravityDeviceId
        batchSaved.value.pressureDeviceId = batch.value.pressureDeviceId
        batchSaved.value.chamberDeviceId = batch.value.chamberDeviceId
        // The route guard reads this store flag synchronously before Vue's next
        // render has recomputed batchChanged() from the updated baseline.
        global.batchChanged = false
        logDebug('BatchView.addBatch()', 'Change to editor', result, batch.value)
        router.push({ name: 'batch', params: { id: batch.value.id } })
      } else {
        global.messageError = 'Failed to add batch'
      }
    } else {
      const success = await batchStore.updateBatch(batch.value)
      logDebug('BatchView.saveBatch()', success)
      if (success) {
        await syncDeviceAssignments(batch.value.id)
        const stepsSaved = await persistSteps(batch.value.id, parsedFermentationSteps.value)
        if (!stepsSaved) {
          global.messageError = 'Saved batch, but failed to save fermentation steps'
          return
        }
        batch.value.fermentationSteps = serializeFermentationSteps(parsedFermentationSteps.value)
        batchSaved.value = Batch.fromJson(batch.value.toJson())
        batchSaved.value.fermentationSteps = batch.value.fermentationSteps
        batchSaved.value.gravityDeviceId = batch.value.gravityDeviceId
        batchSaved.value.pressureDeviceId = batch.value.pressureDeviceId
        batchSaved.value.chamberDeviceId = batch.value.chamberDeviceId
        global.messageSuccess = 'Saved batch'
      } else {
        global.messageError = 'Failed to save batch'
      }
    }
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
.batch-editor-layout__main {
  padding-right: var(--app-space-inline);
}

.batch-editor-layout__notes {
  padding-left: var(--app-space-inline);
}

@media (max-width: 1023px) {
  .batch-editor-layout__main {
    padding-right: 0;
  }

  .batch-editor-layout__notes {
    /* Keep the shared grid gutter below the breakpoint, but remove the desktop divider. */
    border-left: 0;
    padding-left: 0;
  }
}
</style>
