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
  <section class="api-token-section row q-col-gutter-sm q-mt-sm" aria-labelledby="api-token-heading">
    <div class="col-12"><hr /></div>
    <div class="col-12">
      <p id="api-token-heading" class="text-subtitle2">API Token</p>
    </div>
    <div class="col-md-10">
      <AppTextInput :model-value="token" label="Token" help="" disabled />
    </div>
    <div class="col-md-2 self-end">
      <app-button
        type="button"
        variant="secondary" dense
        :disabled="disabled"
        :title="rotationExplanation"
        :aria-label="rotationExplanation"
        @click="$emit('regenerate')"
      >
        <q-icon name="refresh" /> Regenerate token
      </app-button>
    </div>
    <div class="col-12">
      <p class="text-caption text-grey-7 q-mb-none">
        Regenerating this token immediately invalidates the previous token and requires updating the device configuration.
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { AppTextInput } from '@/ui'

defineProps<{
  token: string
  disabled?: boolean
}>()

defineEmits<{
  regenerate: []
}>()

const rotationExplanation =
  'Regenerate API token. This immediately rotates the token and invalidates the previous device configuration.'
</script>
