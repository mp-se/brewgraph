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

import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import pluginVitest from '@vitest/eslint-plugin'
import tseslint from 'typescript-eslint'
import vueParser from 'vue-eslint-parser'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

const typescriptConfigs = tseslint.configs.recommended.flat(Infinity).map((config) => ({
  ...config,
  ...(config.files?.includes('**/*.ts') ? { files: [...config.files, '**/*.vue'] } : {}),
}))

export default [
  {
    name: 'app/files-to-lint',
    files: ['**/*.{js,mjs,jsx,ts,mts,tsx,vue}'],
  },

  {
    name: 'app/files-to-ignore',
    // src/modules/backup/generated/** is ajv's standalone output, written by
    // scripts/build-validators.mjs. It is machine-generated and never hand-edited,
    // so linting it reports on code nobody can act on.
    ignores: [
      '**/dist/**',
      '**/dist-ssr/**',
      '**/coverage/**',
      '**/esp-web-tools/**',
      'src/modules/backup/generated/**',
    ],
  },

  {
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
  },

  js.configs.recommended,
  ...pluginVue.configs['flat/essential'].flat(Infinity),
  ...typescriptConfigs,

  {
    // Parse Vue SFCs with vue-eslint-parser and delegate TypeScript scripts to
    // typescript-eslint, matching the previous Vue-aware config without its
    // vulnerable fast-glob dependency.
    name: 'app/vue-typescript-parser',
    files: ['*.vue', '**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: {
          js: 'espree',
          jsx: 'espree',
          ts: tseslint.parser,
          tsx: tseslint.parser,
        },
        ecmaVersion: 2024,
        ecmaFeatures: { jsx: false },
        extraFileExtensions: ['.vue'],
      },
    },
  },

  {
    // Mixed JS/TS codebase: plain <script setup> blocks are still allowed
    // while views are migrated to lang="ts" incrementally.
    name: 'app/allow-plain-script-blocks',
    files: ['**/*.vue'],
    rules: {
      'vue/block-lang': ['error', { script: { lang: 'ts', allowNoLang: true } }],
    },
  },

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*', 'vitest.setup.js'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },

  {
    // One way to call the API: auth, timeout, error handling and logging live in apiClient.
    name: 'app/no-raw-fetch',
    files: ['src/**/*.{js,ts,vue}'],
    ignores: ['src/modules/apiClient.ts', 'src/**/__tests__/**'],
    rules: {
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Use apiFetch/apiJson/apiOk from @/modules/apiClient.' },
      ],
      'no-restricted-properties': [
        'error',
        { object: 'window', property: 'fetch', message: 'Use @/modules/apiClient.' },
        { object: 'globalThis', property: 'fetch', message: 'Use @/modules/apiClient.' },
      ],
    },
  },

  {
    // Build/CI tooling scripts run under Node, not the browser.
    name: 'app/node-scripts',
    files: ['scripts/**/*.mjs'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
  skipFormatting
]
