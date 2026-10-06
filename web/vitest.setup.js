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

import { vi } from 'vitest'
import { config } from '@vue/test-utils'
import { ClosePopup, Quasar, QBtn, QToggle, QTooltip, QBtnDropdown, QMenu, QCard, QCardSection, QCardActions, QItem, QItemSection, QList, QSpace } from 'quasar'

// The app's compatibility controls are real Quasar components. Install the
// plugin once for every mount so component tests exercise their rendered DOM
// instead of relying on an application-only provide.
config.global.plugins = [Quasar]
config.global.directives = { ClosePopup }
config.global.components = {
  AppButton: {
    inheritAttrs: false,
    props: { variant: String, dense: Boolean },
    template: '<button v-bind="$attrs" :class="[\'app-button\', variant && `app-button--${variant}`, dense && \'app-button--dense\']"><slot /></button>'
  },
  QBtn, QToggle, QTooltip, QBtnDropdown, QMenu, QItem, QItemSection, QList,
  QIcon: { template: '<i />' },
  QMarkupTable: { inheritAttrs: false, template: '<table v-bind="$attrs"><slot /></table>' },
  QDialog: { template: '<div><slot /></div>' }, QCard, QCardSection, QCardActions, QSpace
}

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn()
}

global.localStorage = localStorageMock
