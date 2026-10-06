/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { defineConfig, devices } from '@playwright/test'
import process from 'node:process'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.parity.spec.js',
  fullyParallel: false,
  timeout: 300_000,
  reporter: 'list',
  outputDir: process.env.PARITY_OUTPUT_DIR ?? './test-results-parity',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.WEB_PARITY_URL ?? 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort',
    url: process.env.WEB_PARITY_URL ?? 'http://127.0.0.1:5174',
    reuseExistingServer: true,
    timeout: 30_000
  }
})
