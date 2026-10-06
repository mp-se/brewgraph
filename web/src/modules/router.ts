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

import { ref } from 'vue'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { global } from '@/modules/pinia'
import { logDebug } from '@/ui'

const HomeView = () => import('@/views/HomeView.vue')
const DeviceView = () => import('@/views/DeviceView.vue')
const DeviceLogView = () => import('@/views/DeviceLogView.vue')
const DeviceListView = () => import('@/views/DeviceListView.vue')
const BatchView = () => import('@/views/BatchView.vue')
const BatchListView = () => import('@/views/BatchListView.vue')
const BatchGravityListView = () => import('@/views/BatchGravityListView.vue')
const BatchGravityTestView = () => import('@/views/BatchGravityTestView.vue')
const BatchGravityGraphView = () => import('@/views/BatchGravityGraphView.vue')
const BatchGravityGraphCompareView = () => import('@/views/BatchGravityGraphCompareView.vue')
const BatchPressureGraphView = () => import('@/views/BatchPressureGraphView.vue')
const BatchPressureListView = () => import('@/views/BatchPressureListView.vue')
const BatchTempChartView = () => import('@/views/BatchTempChartView.vue')
const BatchTempListView = () => import('@/views/BatchTempListView.vue')
const BatchFermentationControlView = () => import('@/views/BatchFermentationControlView.vue')
const AboutView = () => import('@/views/AboutView.vue')
const SettingsView = () => import('@/views/SettingsView.vue')
const BackupView = () => import('@/views/BackupView.vue')
const SupportView = () => import('@/views/SupportView.vue')
const SystemLogView = () => import('@/views/SystemLogView.vue')
const IngestionErrorView = () => import('@/views/IngestionErrorView.vue')
const IntegrationsView = () => import('@/views/IntegrationsView.vue')
const NotFoundView = () => import('@/views/NotFoundView.vue')
const TapListView = () => import('@/views/TapListView.vue')
const TapView = () => import('@/views/TapView.vue')
const VesselListView = () => import('@/views/VesselListView.vue')
const VesselView = () => import('@/views/VesselView.vue')
const VesselPourListView = () => import('@/views/VesselPourListView.vue')

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/device', name: 'device-list', component: DeviceListView },
  { path: '/device/log/:id', name: 'device-log', component: DeviceLogView },
  { path: '/device/:id', name: 'device', component: DeviceView },
  { path: '/batch', name: 'batch-list', component: BatchListView },
  { path: '/batch/compare', name: 'batch-compare-view', component: BatchGravityGraphCompareView },
  { path: '/batch/:id', name: 'batch', component: BatchView },
  {
    path: '/batch/:id/gravity/graph',
    name: 'batch-gravity-graph',
    component: BatchGravityGraphView
  },
  {
    path: '/batch/:id/fermentation-control',
    name: 'batch-fermentation-control',
    component: BatchFermentationControlView
  },
  { path: '/batch/:id/gravity', name: 'batch-gravity-list', component: BatchGravityListView },
  {
    path: '/batch/:id/pressure/graph',
    name: 'batch-pressure-graph',
    component: BatchPressureGraphView
  },
  { path: '/batch/:id/pressure', name: 'batch-pressure-list', component: BatchPressureListView },
  { path: '/batch/:id/temp/chart', name: 'batch-temp-chart', component: BatchTempChartView },
  { path: '/batch/:id/temp', name: 'batch-temp-list', component: BatchTempListView },
  {
    path: '/batch/:id/gravity/test',
    name: 'batch-gravity-test-list',
    component: BatchGravityTestView
  },
  { path: '/settings', name: 'settings', component: SettingsView },
  { path: '/other/backup', name: 'backup', component: BackupView },
  { path: '/other/support', name: 'support', component: SupportView },
  { path: '/other/system', name: 'system_log', component: SystemLogView },
  { path: '/other/ingestion', name: 'ingestion_log', component: IngestionErrorView },
  { path: '/other/integrations', name: 'integrations', component: IntegrationsView },
  { path: '/other/about', name: 'about', component: AboutView },
  { path: '/cellar/taps', name: 'tap-list', component: TapListView },
  { path: '/cellar/taps/:id', name: 'tap', component: TapView },
  { path: '/cellar/vessels', name: 'vessel-list', component: VesselListView },
  { path: '/cellar/vessels/:id', name: 'vessel', component: VesselView },
  { path: '/cellar/vessels/:id/pours', name: 'vessel-pour-list', component: VesselPourListView },
  { path: '/:catchAll(.*)', name: '404', component: NotFoundView }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router

export const handleNavigationEnd = (
  globalStore: typeof global,
  to: unknown,
  from: unknown
): boolean => {
  logDebug('router.handleNavigationEnd()', to, from)

  if (globalStore && typeof globalStore.clearMessages === 'function') {
    globalStore.clearMessages()
  }
  if (globalStore) {
    // Every editor's unsaved flag: one left set after the user chose to leave without saving
    // makes the 'unsaved changes' prompt reappear on every later screen.
    globalStore.batchChanged = false
    globalStore.deviceChanged = false
    globalStore.tapChanged = false
    globalStore.vesselChanged = false
  }
  return true
}

router.beforeEach(() => {
  if (global.hasUnsavedChanges) {
    return window.confirm('You have unsaved changes. Leave without saving?')
  }
  return true
})

router.afterEach((to, from) => {
  return handleNavigationEnd(global, to, from)
})

export { routes }

interface NavItem {
  label: string
  icon: string
  path: string
  subs: { label: string; path: string; external?: boolean }[]
}

const items = ref<NavItem[]>([
  { label: 'Home', icon: 'home', path: '/', subs: [] },
  { label: 'Device', icon: 'memory', path: '/device', subs: [] },
  { label: 'Batch', icon: 'show_chart', path: '/batch', subs: [] },
  {
    label: 'Cellar',
    icon: 'construction',
    path: '/cellar',
    subs: [
      { label: 'Taps', path: '/cellar/taps' },
      { label: 'Vessels', path: '/cellar/vessels' },
      // Opens the tap board in a new window. It is the public display — a separate
      // static app in its own container, not a route in this SPA, and never
      // authenticated.
      { label: 'Tap Board', path: '/public', external: true }
    ]
  },
  { label: 'Settings', icon: 'settings', path: '/settings', subs: [] },
  {
    label: 'Other',
    icon: 'more_horiz',
    path: '/other',
    subs: [
      { label: 'Backup & Restore', path: '/other/backup' },
      { label: 'System log', path: '/other/system' },
      { label: 'Ingestion log', path: '/other/ingestion' },
      { label: 'Integrations', path: '/other/integrations' },
      { label: 'About', path: '/other/about' }
    ]
  }
])

export { items }
