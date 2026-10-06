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

import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      setupFiles: ['./vitest.setup.js'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json-summary', 'json'],
        include: [
          'src/modules/**/*.ts',
          'src/modules/**/*.js',
          'src/views/BatchView.vue',
          'src/views/BackupView.vue',
          'src/views/BatchListView.vue',
          'src/views/BatchPressureListView.vue',
          'src/views/BatchPressureGraphView.vue',
          'src/views/BatchGravityGraphView.vue',
          'src/views/BatchGravityListView.vue',
          'src/views/BatchTempChartView.vue',
          'src/views/DeviceLogView.vue',
          'src/views/DeviceListView.vue',
          'src/views/DeviceView.vue',
          'src/views/HomeView.vue',
          'src/views/IngestionErrorView.vue',
          'src/views/SettingsView.vue',
          'src/views/SystemLogView.vue',
          'src/views/TapListView.vue',
          'src/views/VesselListView.vue'
        ],
        exclude: [
          'src/modules/**/__tests__/**',
          'src/modules/backup/generated/**',
          'src/modules/pinia/**',
          'src/modules/router.ts'
        ],
        thresholds: {
          statements: 75,
          branches: 75,
          functions: 75,
          lines: 75,
          perFile: true
        }
      }
    },
    resolve: {
      alias: {
        // Vitest runs in jsdom, so it needs Quasar's browser build rather
        // than Vite's server/SSR conditional export.
        quasar: 'quasar/dist/quasar.client.js'
      }
    }
  })
)
