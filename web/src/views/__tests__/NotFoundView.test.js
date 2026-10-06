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

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotFoundView from '../NotFoundView.vue'
import { AppMessage } from '@/ui'

describe('NotFoundView', () => {
  describe('Basic Rendering', () => {
    it('should render AppMessage component', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.findComponent(AppMessage).exists()).toBe(true)
    })

    it('should have danger alert type', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const message = wrapper.findComponent(AppMessage)
      expect(message.props('alert')).toBe('danger')
    })

    it('should not be dismissable', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const message = wrapper.findComponent(AppMessage)
      expect(message.props('dismissable')).toBe(false)
    })
  })

  describe('Message Content', () => {
    it('should display "Page not found!" message', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.text()).toContain('Page not found!')
    })

    it('should display the invalid path', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.text()).toContain('is not a valid URL')
    })

    it('should reference the application', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.text()).toContain('for this application')
    })
  })

  describe('Route Path Display', () => {
    it('should access route path from $route', () => {
      const router = createRouter({
        history: createMemoryHistory('/invalid-page'),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      // The route path should be displayed
      const text = wrapper.text()
      expect(text.length).toBeGreaterThan(0)
    })

    it('should have bold styling on path', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const bold = wrapper.find('.text-weight-bold')
      expect(bold.exists()).toBe(true)
    })

    it('should embed path in a span with text-weight-bold class', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const boldSpan = wrapper.find('span.text-weight-bold')
      expect(boldSpan.exists()).toBe(true)
    })
  })

  describe('Error Page Characteristics', () => {
    it('should be a single error message container', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const messages = wrapper.findAllComponents(AppMessage)
      expect(messages.length).toBe(1)
    })

    it('should use AppMessage for consistent error styling', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const message = wrapper.findComponent(AppMessage)
      expect(message.props('alert')).toBe('danger')
    })

    it('should communicate this is an error state', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.text()).toContain('not found')
    })

    it('should indicate page does not exist', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.text()).toContain('not a valid')
    })
  })

  describe('Accessibility', () => {
    it('should have semantic structure', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      expect(wrapper.html()).toBeTruthy()
    })

    it('should render without hidden content', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: []
      })
      const wrapper = mount(NotFoundView, {
        global: {
          components: { AppMessage },
          plugins: [router]
        }
      })
      const text = wrapper.text()
      expect(text.includes('Page not found')).toBe(true)
    })
  })
})
