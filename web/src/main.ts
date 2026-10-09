/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

import { createApp } from 'vue'
import {
  Quasar,
  QToolbar,
  QToolbarTitle,
  QBtn,
  QBtnDropdown,
  QMenu,
  QDialog,
  QCard,
  QCardSection,
  QCardActions,
  QBanner,
  QBtnToggle,
  QTabs,
  QTab,
  QInput,
  QIcon,
  QMarkupTable,
  QList,
  QItem,
  QItemSection,
  QSpace,
  QBadge,
  QSpinner,
  QToggle,
  QTooltip,
  ClosePopup
} from 'quasar'
import App from './App.vue'
import { brand } from './ui/theme'

const app = createApp(App)

app.use(Quasar, {
  components: {
    QToolbar,
    QToolbarTitle,
    QBtn,
    QBtnDropdown,
    QMenu,
    QDialog,
    QCard,
    QCardSection,
    QCardActions,
    QBanner,
    QBtnToggle,
    QTabs,
    QTab,
    QInput,
    QIcon,
    QMarkupTable,
    QList,
    QItem,
    QItemSection,
    QSpace,
    QBadge,
    QSpinner,
    QToggle,
    QTooltip
  },
  directives: { ClosePopup },
  config: {
    brand
  }
})

import piniaInstance from './modules/pinia'
app.use(piniaInstance)

import router from './modules/router'
app.use(router)

import {
  AppMessage,
  AppCard,
  AppFileUpload,
  AppProgress,
  AppField,
  AppTextInput,
  AppReadonlyInput,
  AppSelect,
  AppTextArea,
  AppInputNumber,
  AppToggle,
  AppRadioGroup,
  AppDropdown,
  AppDataDialog,
  AppConfirmDialog,
  AppSelectDialog
} from '@/ui'
import AppInputDate from '@/components/AppInputDate.vue'

import GravityStatsFragment from '@/fragments/GravityStatsFragment.vue'
import PressureStatsFragment from '@/fragments/PressureStatsFragment.vue'
import LifeEstimates from '@/views/LifeEstimates.vue'

app.component('AppMessage', AppMessage)
app.component('AppDropdown', AppDropdown)
app.component('AppCard', AppCard)
app.component('AppFileUpload', AppFileUpload)
app.component('AppProgress', AppProgress)
app.component('AppField', AppField)
app.component('AppTextInput', AppTextInput)
app.component('AppReadonlyInput', AppReadonlyInput)
app.component('AppSelect', AppSelect)
app.component('AppTextArea', AppTextArea)
app.component('AppInputNumber', AppInputNumber)
app.component('AppRadioGroup', AppRadioGroup)
app.component('AppToggle', AppToggle)

app.component('AppDataDialog', AppDataDialog)
app.component('AppConfirmDialog', AppConfirmDialog)
app.component('AppSelectDialog', AppSelectDialog)
app.component('AppInputDate', AppInputDate)

app.component('GravityStatsFragment', GravityStatsFragment)
app.component('PressureStatsFragment', PressureStatsFragment)
app.component('LifeEstimates', LifeEstimates)

import IconListUl from './components/IconListUl.vue'
import AppButton from './components/AppButton.vue'

app.component('IconListUl', IconListUl)
app.component('AppButton', AppButton)

import 'quasar/dist/quasar.css'
import '@quasar/extras/material-icons/material-icons.css'
import './styles/app-theme.css'

app.mount('#app')
