<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph
-->

<template>
  <app-button type="button" variant="outline-secondary" class="app-width-2" :disabled="disabled" @click="openDialog">
    {{ button }}
  </app-button>
  <q-dialog v-model="dialogOpen"><q-card class="app-dialog-card" style="width: min(900px, calc(100vw - 32px))">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6">{{ title }}</div><q-space /><q-btn icon="close" flat round dense v-close-popup aria-label="Close" />
        </q-card-section>
        <q-card-section>
          <pre>{{ modelValue }}</pre>
        </q-card-section>
        <q-card-actions align="right" class="app-dialog-actions">
          <span v-if="copyStatus" class="q-mr-auto text-caption" :class="copyStatusClass">{{ copyStatus }}</span>
          <app-button type="button" variant="secondary" :disabled="!modelValue" @click="copy">
            <q-icon name="content_copy" /> Copy
          </app-button>
          <q-btn flat no-caps label="Close" v-close-popup />
        </q-card-actions>
  </q-card></q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { copyToClipboard } from '@/modules/utils'

const props = withDefaults(defineProps<{
  modelValue?: string
  title?: string
  button?: string
  disabled?: boolean
}>(), {
  modelValue: '',
  title: '',
  button: 'View',
  disabled: false
})
const emit = defineEmits<{ click: [] }>()

const dialogOpen = ref(false)
const copied = ref<boolean | null>(null)
const copyStatus = computed(() =>
  copied.value === null ? '' : copied.value ? 'Copied to clipboard.' : 'Unable to copy.'
)
const copyStatusClass = computed(() => (copied.value ? 'text-success' : 'text-danger'))

function openDialog() {
  emit('click')
  dialogOpen.value = true
}

async function copy() {
  copied.value = await copyToClipboard(props.modelValue)
  setTimeout(() => { copied.value = null }, 2000)
}

defineExpose({ copy })
</script>
