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
    <AppPageHeader title="Settings" />

    <form @submit.prevent="saveSettings" class="app-validation" novalidate>
      <div class="row q-col-gutter-md">
        <div class="col-md-3">
          <div class="app-setting-toggle">
            <label class="app-field-label" for="temperature-format">Temperature Format</label>
            <QBtnToggle
            id="temperature-format"
            v-model="config.temperatureFormat"
            :options="temperatureOptions"
            :disable="global.disabled"
            class="app-setting-toggle__buttons"
            no-caps
            unelevated
            toggle-color="primary"
            toggle-text-color="white"
            aria-label="Temperature Format"
          />
          </div>
        </div>
        <div class="col-md-3">
          <div class="app-setting-toggle">
            <label class="app-field-label" for="gravity-format">Gravity Format</label>
            <QBtnToggle
            id="gravity-format"
            v-model="config.gravityFormat"
            :options="gravityOptions"
            :disable="global.disabled"
            class="app-setting-toggle__buttons"
            no-caps
            unelevated
            toggle-color="primary"
            toggle-text-color="white"
            aria-label="Gravity Format"
          />
          </div>
        </div>
        <div class="col-md-3">
          <div class="app-setting-toggle">
            <label class="app-field-label" for="pressure-format">Pressure Format</label>
            <QBtnToggle
            id="pressure-format"
            v-model="config.pressureFormat"
            :options="pressureOptions"
            :disable="global.disabled"
            class="app-setting-toggle__buttons"
            no-caps
            unelevated
            toggle-color="primary"
            toggle-text-color="white"
            aria-label="Pressure Format"
          />
          </div>
        </div>
        <div class="col-md-3">
          <div class="app-setting-toggle">
            <label class="app-field-label" for="volume-format">Volume Format</label>
            <QBtnToggle
            id="volume-format"
            v-model="config.volumeFormat"
            :options="volumeOptions"
            :disable="global.disabled"
            class="app-setting-toggle__buttons"
            no-caps
            unelevated
            toggle-color="primary"
            toggle-text-color="white"
            aria-label="Volume Format"
          />
          </div>
        </div>

        <div class="col-md-12">
          <hr />
        </div>

        <div class="col-md-4">
          <div class="app-setting-toggle">
            <label class="app-field-label" for="theme">Theme</label>
            <QBtnToggle
            id="theme"
            v-model="preferences.dark_mode"
            :options="darkModeOptions"
            :disable="global.disabled"
            class="app-setting-toggle__buttons"
            no-caps
            unelevated
            toggle-color="primary"
            toggle-text-color="white"
            aria-label="Theme"
          />
          </div>
        </div>
        <!-- 
        <div class="col-md-6">
          <AppInputNumber
            v-model="config.mdnsTimeout"
            min="1"
            max="60"
            label="MDNS Search Timeout"
            width="2"
            help="How long time will be scan for MDNS devices on the local network"
            :disabled="global.disabled"
          >
          </AppInputNumber>
        </div>-->
      </div>

      <div class="row q-col-gutter-sm">
        <div class="col-md-12">
          <hr />
        </div>
        <div class="col-md-3">
          <app-button
            type="submit"
            variant="primary" class="app-width-2"
            :disabled="global.disabled || isSaving || !global.configChanged"
            :aria-busy="isSaving"
          >
            <span
              v-if="isSaving"
              class="app-spinner app-spinner--small"
              role="status"
              aria-hidden="true"
            ></span>
            &nbsp;Save
          </app-button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { QBtnToggle } from 'quasar'
import { global, config, preferences } from '@/modules/pinia'
import { validateCurrentForm } from '@/modules/utils'
import { logDebug } from '@/ui'
import AppPageHeader from '@/components/AppPageHeader.vue'
import {
  temperatureOptions,
  gravityOptions,
  pressureOptions,
  volumeOptions
} from '@/modules/classes'

const darkModeOptions = [
  { label: 'Dark Mode', value: true },
  { label: 'Day Mode', value: false }
]

const isSaving = ref(false)

const saveSettings = async () => {
  logDebug('SettingsView.saveSettings()')

  if (!validateCurrentForm()) return

  isSaving.value = true
  try {
    const success = await config.save()
    if (success) global.messageSuccess = 'Settings saved'
    else global.messageError = 'Failed to save settings'
  } finally {
    isSaving.value = false
  }
}
</script>
