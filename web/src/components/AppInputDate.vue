<!-- Copyright (c) 2024-2026 Magnus Persson SPDX-License-Identifier: GPL-3.0-only -->
<template>
  <div class="app-form-field">
    <label v-if="label" :for="id" class="app-field-label">{{ label }}</label>
    <QInput :id="id" :model-value="modelValue ?? ''" type="date" outlined dense hide-bottom-space :disable="disabled" :error="Boolean(errorMessage)" :error-message="errorMessage" v-bind="$attrs" @update:model-value="$emit('update:modelValue', String($event ?? ''))">
      <template #append><QIcon name="event" class="cursor-pointer"><QPopupProxy cover transition-show="scale" transition-hide="scale"><QDate :model-value="modelValue ?? ''" mask="YYYY-MM-DD" @update:model-value="$emit('update:modelValue', String($event ?? ''))"><div class="row items-center justify-end q-gutter-sm"><QBtn v-close-popup label="Close" color="primary" flat /></div></QDate></QPopupProxy></QIcon></template>
    </QInput>
    <div v-if="help" class="app-field-help">{{ help }}</div>
  </div>
</template>
<script setup lang="ts">
import { QBtn, QDate, QIcon, QInput, QPopupProxy } from 'quasar'
defineOptions({ inheritAttrs: false })
defineProps<{ id?: string; modelValue?: string | null; label?: string; help?: string; disabled?: boolean; errorMessage?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
