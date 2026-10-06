<!-- Copyright (c) 2024-2026 Magnus Persson SPDX-License-Identifier: GPL-3.0-only -->
<template>
  <div class="row q-col-gutter-md batch-editor-actions">
    <div class="col-md-12 batch-editor-section-divider"><hr /></div>
    <div class="col-md-12 app-button-row" data-testid="batch-primary-actions">
      <app-button
        type="submit"
        variant="primary" class="app-width-2"
        :disabled="disabled || saving || !hasChanges || !batchName || isArchived"
        :aria-busy="saving"
      >
        <span v-if="saving" class="app-spinner app-spinner--small" role="status" aria-hidden="true"></span>
        <q-icon name="save" /> Save
      </app-button>
      <router-link :to="{ name: 'batch-list' }">
        <app-button type="button" variant="secondary" class="app-width-2">
          <q-icon name="cancel" /> Cancel
        </app-button>
      </router-link>
    </div>
    <div class="col-md-12">
      <section class="batch-editor-actions__secondary" data-testid="batch-secondary-actions" aria-labelledby="batch-secondary-actions-title">
        <h2 id="batch-secondary-actions-title" class="batch-editor-actions__title">Import, export and status</h2>
        <div class="app-button-row">
          <BatchBeerXmlImportFragment @imported="$emit('imported', $event)" />
          <BatchBrewfatherLinkFragment
            @linked="$emit('linked', $event)"
            @cleared="$emit('cleared')"
          />
          <app-button
            type="button"
            variant="outline-secondary" class="app-width-2"
            :disabled="disabled || isNew"
            title="Download this batch as a BrewGraph JSON export"
            @click="$emit('export')"
          >
            <q-icon name="data_object" /> Export
          </app-button>
          <app-button
            v-if="!isNew && !isArchived"
            type="button"
            variant="outline-secondary" class="app-width-2"
            :disabled="disabled"
            @click="$emit('archive')"
          >
            <q-icon name="archive" /> Archive
          </app-button>
          <app-button
            v-if="!isNew && isArchived"
            type="button"
            variant="outline-secondary" class="app-width-2"
            :disabled="disabled"
            @click="$emit('unarchive')"
          >
            <q-icon name="upload" /> Un-archive
          </app-button>
          <router-link
            v-if="canFermentationControl"
            :to="{ name: 'batch-fermentation-control', params: { id: batchId } }"
          >
            <app-button
              type="button"
              variant="outline-secondary" class="app-width-3"
              :disabled="fermentationControlDisabled"
            >
              Fermentation Control
            </app-button>
          </router-link>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import BatchBeerXmlImportFragment from '@/fragments/BatchBeerXmlImportFragment.vue'
import BatchBrewfatherLinkFragment from '@/fragments/BatchBrewfatherLinkFragment.vue'

interface Props {
  disabled?: boolean
  saving?: boolean
  hasChanges?: boolean
  batchName?: string
  isNew?: boolean
  isArchived?: boolean
  canFermentationControl?: boolean
  fermentationControlDisabled?: boolean
  batchId?: string | number
}

withDefaults(defineProps<Props>(), {
  disabled: false,
  saving: false,
  hasChanges: false,
  batchName: '',
  isNew: false,
  isArchived: false,
  canFermentationControl: false,
  fermentationControlDisabled: false,
  batchId: ''
})

defineEmits<{
  export: []
  archive: []
  unarchive: []
  imported: [batch: unknown]
  linked: [batch: unknown]
  cleared: []
}>()
</script>

<style scoped>
.batch-editor-actions {
  margin-top: 24px;
}

.batch-editor-actions__secondary {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}

.batch-editor-actions__title {
  margin: 0 0 8px;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.batch-editor-section-divider {
  padding-top: 4px;
  padding-bottom: 4px;
}
</style>
