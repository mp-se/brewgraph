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
  <div class="col-12 q-mt-md">
    <div class="app-legacy-card">
      <div
        class="app-legacy-card__header row justify-between items-center"
        style="cursor: pointer"
        @click="open = !open"
      >
        <span>How to configure this device</span>
        <q-icon :name="open ? 'expand_less' : 'expand_more'" />
      </div>

      <div v-if="open" class="app-legacy-card__body">
        <template v-if="setup">
          <p class="q-mb-sm">{{ setup.intro }}</p>
          <q-markup-table class="app-table app-table--dense app-table--borderless">
            <tbody>
              <tr v-if="setup.separateFields">
                <td class="text-weight-medium" style="width:160px">Server address</td>
                <td><div class="row items-center q-gutter-sm"><code class="col-grow">{{ host }}</code><app-button type="button" variant="outline-secondary" dense @click="copy(host)"><q-icon name="content_copy" /> Copy</app-button></div></td>
              </tr>
              <tr>
                <td class="text-weight-medium" style="width:160px">Server URL</td>
                <td><div class="row items-center q-gutter-sm"><code class="col-grow">{{ serverUrl }}</code><app-button type="button" variant="outline-secondary" dense @click="copy(serverUrl)"><q-icon name="content_copy" /> Copy</app-button></div></td>
              </tr>
              <template v-if="setup.separateFields">
                <tr><td class="text-weight-medium">Port</td><td><code>80</code></td></tr>
                <tr><td class="text-weight-medium">Use SSL</td><td>disabled (local install)</td></tr>
              </template>
              <tr>
                <td class="text-weight-medium">Token</td>
                <td><div class="row items-center q-gutter-sm"><code class="col-grow">{{ token }}</code><app-button type="button" variant="outline-secondary" dense @click="copy(token)"><q-icon name="content_copy" /> Copy</app-button></div></td>
              </tr>
            </tbody>
          </q-markup-table>
        </template>

        <p v-else class="text-grey-7 q-mb-none">No setup instructions available for this device type.</p>

        <p v-if="copied" class="text-positive q-mt-sm q-mb-none text-caption">Copied to clipboard.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { copyToClipboard } from '@/modules/utils'
import { deviceSetupFor } from '@/modules/deviceSetup'

const props = defineProps<{
  deviceType: string
  token: string
  hasReadings?: boolean
}>()

const setup = computed(() => deviceSetupFor(props.deviceType))

const host = window.location.hostname + (window.location.port ? `:${window.location.port}` : '')

// iSpindel's UI takes the bare path next to a separate host field; the others take a full URL.
const serverUrl = computed(() =>
  setup.value?.separateFields ? setup.value.path : `http://${host}${setup.value?.path ?? ''}`
)

// Expanded by default on fresh devices (no readings yet); collapsed once posting
const open = ref(!props.hasReadings)

const copied = ref(false)

async function copy(text: string) {
  if (await copyToClipboard(text)) {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}
</script>
