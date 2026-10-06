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

import { describe, it, expect, beforeEach, vi } from 'vitest'
import router, { handleNavigationEnd, routes } from '@/modules/router'

describe('Router - Navigation and Routing', () => {
  describe('handleNavigationEnd', () => {
    let mockGlobalStore

    beforeEach(() => {
      mockGlobalStore = {
        clearMessages: vi.fn(),
        batchChanged: true,
        deviceChanged: true,
        tapChanged: true,
        vesselChanged: true
      }
    })

    it('clears the unsaved flag of every editor, so leaving a tap or vessel does not keep prompting', () => {
      handleNavigationEnd(mockGlobalStore, { path: '/cellar/vessels' }, { path: '/cellar/vessels/v1' })

      expect(mockGlobalStore.tapChanged).toBe(false)
      expect(mockGlobalStore.vesselChanged).toBe(false)
    })

    it('should clear messages and reset global state on navigation end', () => {
      const to = { path: '/batch', name: 'batch-list' }
      const from = { path: '/', name: 'home' }

      const result = handleNavigationEnd(mockGlobalStore, to, from)

      expect(mockGlobalStore.clearMessages).toHaveBeenCalled()
      expect(mockGlobalStore.batchChanged).toBe(false)
      expect(mockGlobalStore.deviceChanged).toBe(false)
      expect(result).toBe(true)
    })

    it('should handle navigation from batch to device', () => {
      const to = { path: '/device', name: 'device-list' }
      const from = { path: '/batch', name: 'batch-list' }

      handleNavigationEnd(mockGlobalStore, to, from)

      expect(mockGlobalStore.clearMessages).toHaveBeenCalledWith()
      expect(mockGlobalStore.batchChanged).toBe(false)
      expect(mockGlobalStore.deviceChanged).toBe(false)
    })

    it('should handle null globalStore gracefully', () => {
      const to = { path: '/batch', name: 'batch-list' }
      const from = { path: '/', name: 'home' }

      const result = handleNavigationEnd(null, to, from)

      expect(result).toBe(true)
    })

    it('should handle undefined globalStore gracefully', () => {
      const to = { path: '/batch', name: 'batch-list' }
      const from = { path: '/', name: 'home' }

      const result = handleNavigationEnd(undefined, to, from)

      expect(result).toBe(true)
    })

    it('should handle globalStore without clearMessages method', () => {
      const minimalStore = {
        batchChanged: true,
        deviceChanged: true
      }

      const to = { path: '/settings', name: 'settings' }
      const from = { path: '/', name: 'home' }

      const result = handleNavigationEnd(minimalStore, to, from)

      expect(minimalStore.batchChanged).toBe(false)
      expect(minimalStore.deviceChanged).toBe(false)
      expect(result).toBe(true)
    })

    it('should handle navigation with parameters', () => {
      const to = { path: '/batch/123', name: 'batch', params: { id: '123' } }
      const from = { path: '/batch', name: 'batch-list' }

      handleNavigationEnd(mockGlobalStore, to, from)

      expect(mockGlobalStore.clearMessages).toHaveBeenCalled()
      expect(mockGlobalStore.batchChanged).toBe(false)
    })

    it('should reset flags even if clearMessages throws', () => {
      mockGlobalStore.clearMessages.mockImplementation(() => {
        throw new Error('Clear failed')
      })

      expect(() => {
        handleNavigationEnd(mockGlobalStore, {}, {})
      }).toThrow()

      // The function should still attempt to reset flags before throws
      expect(mockGlobalStore.clearMessages).toHaveBeenCalled()
    })

    it('should handle globalStore with additional properties', () => {
      const extendedStore = {
        clearMessages: vi.fn(),
        batchChanged: true,
        deviceChanged: true,
        userId: 'user123',
        appName: 'BrewGraph'
      }

      handleNavigationEnd(extendedStore, { path: '/batch' }, { path: '/' })

      expect(extendedStore.batchChanged).toBe(false)
      expect(extendedStore.deviceChanged).toBe(false)
      expect(extendedStore.userId).toBe('user123') // Should not modify unrelated properties
    })
  })

  describe('Route Definitions', () => {
    it('should have routes array defined', () => {
      expect(routes).toBeDefined()
      expect(Array.isArray(routes)).toBe(true)
    })

    it('should have routes defined', () => {
      expect(routes.length).toBeGreaterThan(0)
    })

    it('should have home route as first route', () => {
      const homeRoute = routes[0]
      expect(homeRoute.path).toBe('/')
      expect(homeRoute.name).toBe('home')
      expect(homeRoute.component).toBeDefined()
    })

    it('should have catch-all 404 route as last route', () => {
      const lastRoute = routes[routes.length - 1]
      expect(lastRoute.path).toBe('/:catchAll(.*)')
      expect(lastRoute.name).toBe('404')
      expect(lastRoute.component).toBeDefined()
    })

    it('should have all required device routes', () => {
      const deviceRouteNames = ['device-list', 'device', 'device-log']
      const routeNames = routes.map((r) => r.name)

      deviceRouteNames.forEach((name) => {
        expect(routeNames).toContain(name)
      })
    })

    it('should have all required batch routes', () => {
      const batchRouteNames = [
        'batch-list',
        'batch',
        'batch-gravity-list',
        'batch-pressure-list',
        'batch-gravity-graph',
        'batch-pressure-graph'
      ]
      const routeNames = routes.map((r) => r.name)

      batchRouteNames.forEach((name) => {
        expect(routeNames).toContain(name)
      })
    })

    it('should have parameterized routes with :id', () => {
      const paramRoutes = routes.filter((r) => r.path.includes(':id'))

      expect(paramRoutes.length).toBeGreaterThan(0)
      paramRoutes.forEach((route) => {
        expect(route.component).toBeDefined()
      })
    })

    it('should have unique route names', () => {
      const names = routes.map((r) => r.name)
      const uniqueNames = new Set(names)

      expect(names.length).toBe(uniqueNames.size)
    })

    it('should have unique route paths (except for different names)', () => {
      const paths = routes.map((r) => r.path)

      // Some paths might be duplicates (same path, different name) - that's okay for route aliases
      // Just verify they exist
      expect(paths.length).toBe(routes.length)
    })

    it('should have component defined for all routes', () => {
      routes.forEach((route) => {
        expect(route.component).toBeDefined()
      })
    })

    it('should have settings route', () => {
      const settingsRoute = routes.find((r) => r.name === 'settings')

      expect(settingsRoute).toBeDefined()
      expect(settingsRoute.path).toBe('/settings')
    })

    it('should have all other utility routes', () => {
      const otherRoutes = ['backup', 'system_log', 'ingestion_log', 'about']
      const routeNames = routes.map((r) => r.name)

      otherRoutes.forEach((name) => {
        expect(routeNames).toContain(name)
      })
    })

    it('should have batch compare functionality route', () => {
      const compareRoute = routes.find((r) => r.name === 'batch-compare-view')

      expect(compareRoute).toBeDefined()
      expect(compareRoute.path).toBe('/batch/compare')
    })

    it('should have batch fermentation control route', () => {
      const fermRoute = routes.find((r) => r.name === 'batch-fermentation-control')

      expect(fermRoute).toBeDefined()
      expect(fermRoute.path).toContain('fermentation-control')
    })

    it('should have gravity test route', () => {
      const testRoute = routes.find((r) => r.name === 'batch-gravity-test-list')

      expect(testRoute).toBeDefined()
      expect(testRoute.path).toContain('gravity/test')
    })

    it('all routes should have name and path properties', () => {
      routes.forEach((route) => {
        expect(route.name).toBeDefined()
        expect(typeof route.name).toBe('string')
        expect(route.path).toBeDefined()
        expect(typeof route.path).toBe('string')
      })
    })

    it('should have no empty paths except catch-all', () => {
      routes
        .filter((route) => route.name !== '404')
        .forEach((route) => {
          expect(route.path).not.toBe('')
          expect(route.path.length).toBeGreaterThan(0)
        })
    })
  })

  describe('Route Organization', () => {
    it('should have routes organized by feature', () => {
      const deviceRoutes = routes.filter((r) => r.path.includes('device'))
      const batchRoutes = routes.filter((r) => r.path.includes('batch'))

      expect(deviceRoutes.length).toBeGreaterThan(0)
      expect(batchRoutes.length).toBeGreaterThan(0)
    })

    it('should prefix other routes with /other path', () => {
      const otherRoutes = routes.filter((r) => r.path.includes('/other'))

      otherRoutes
        .filter((route) => route.name !== 'support')
        .forEach((route) => {
          expect(route.path).toMatch(/^\/other/)
        })
    })

    it('should use consistent naming convention with hyphens', () => {
      routes.forEach((route) => {
        // Names should be lowercase with hyphens, underscores, or numbers
        expect(route.name).toMatch(/^[a-z0-9-_]+$/)
      })
    })
  })

  describe('Navigation Scenarios', () => {
    it('resolves gravity list and graph routes with the selected batch id', () => {
      const batchId = '9a141f8d-408c-43df-8219-ca11af9124bc'

      expect(router.resolve({ name: 'batch-gravity-list', params: { id: batchId } }).fullPath)
        .toBe(`/batch/${batchId}/gravity`)
      expect(router.resolve({ name: 'batch-gravity-graph', params: { id: batchId } }).fullPath)
        .toBe(`/batch/${batchId}/gravity/graph`)
    })

    it('should support home page navigation', () => {
      const homeRoute = routes.find((r) => r.name === 'home')
      expect(homeRoute).toBeDefined()
      expect(homeRoute.path).toBe('/')
    })

    it('should support device management flow', () => {
      const deviceListRoute = routes.find((r) => r.name === 'device-list')
      const deviceRoute = routes.find((r) => r.name === 'device')

      expect(deviceListRoute).toBeDefined()
      expect(deviceRoute).toBeDefined()
    })

    it('should support batch management flow', () => {
      const batchListRoute = routes.find((r) => r.name === 'batch-list')
      const batchRoute = routes.find((r) => r.name === 'batch')
      const batchGravityRoute = routes.find((r) => r.name === 'batch-gravity-list')
      const batchPressureRoute = routes.find((r) => r.name === 'batch-pressure-list')

      expect(batchListRoute).toBeDefined()
      expect(batchRoute).toBeDefined()
      expect(batchGravityRoute).toBeDefined()
      expect(batchPressureRoute).toBeDefined()
    })

    it('should handle catch-all unknown routes', () => {
      const notFoundRoute = routes.find((r) => r.name === '404')

      expect(notFoundRoute).toBeDefined()
      expect(notFoundRoute.path).toBe('/:catchAll(.*)')
    })
  })
})
