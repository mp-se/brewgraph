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

import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The local Docker web gateway owns both API auth and the generated
// /env-config.js token. Keep Vite on a separate origin, but proxy these runtime
// routes through that gateway so development behaves like the deployed SPA.
const devProxyTarget = process.env.BREWGRAPH_DEV_PROXY_TARGET ?? 'http://127.0.0.1:80'
const devProxy = { target: devProxyTarget, changeOrigin: true }

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue()
  ],
  // A fixed port makes local proxy rules stable.
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': devProxy,
      '/events': devProxy,
      '/health': devProxy,
      '/ingest': devProxy,
      '/env-config.js': devProxy
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@brewgraph/core': fileURLToPath(new URL('./src/core/index.ts', import.meta.url)),
    }
  }
})
