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
import PressureStatsFragment from '../PressureStatsFragment.vue'
import { AppReadonlyInput } from '@/ui'
import { AppField } from '@/ui'

describe('PressureStatsFragment - Pressure Statistics Display', () => {
  const samplePressureStats = {
    pressure: {
      maxString: '0.690 Bar',
      minString: '0.345 Bar'
    },
    readings: 12,
    averageIntervalString: '2.4 hours',
    temperature: {
      maxString: '22.00 C',
      minString: '18.00 C'
    },
    date: {
      firstDate: '2024-01-20',
      lastDate: '2024-01-25'
    }
  }

  describe('Basic Rendering', () => {
    it('should render when pressureStats is provided', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(true)
    })

    it('should not render when pressureStats is null', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: null },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(false)
    })

    it('should have row class for layout', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(true)
    })
  })

  describe('Display Fields', () => {
    it('should display high pressure', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Max pressure')
    })

    it('should display low pressure', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Min pressure')
    })

    it('should display reading count', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Readings')
    })

    it('should display average interval', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Avg interval')
    })

    it('should display temperature statistics', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Temp min')
      expect(wrapper.text()).toContain('Temp max')
    })

    it('should display first and last dates', () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('First')
      expect(wrapper.text()).toContain('Last')
    })
  })

  describe('V-Model Binding', () => {
    it('should handle null model value transitions', async () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })

      expect(wrapper.find('.row').exists()).toBe(true)

      await wrapper.setProps({ modelValue: null })
      expect(wrapper.find('.row').exists()).toBe(false)

      await wrapper.setProps({ modelValue: samplePressureStats })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should preserve model state through prop updates', async () => {
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: samplePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })

      const updates = [
        { ...samplePressureStats, readings: 15 },
        { ...samplePressureStats, readings: 18 },
        { ...samplePressureStats, readings: 22 }
      ]

      for (const update of updates) {
        await wrapper.setProps({ modelValue: update })
        expect(wrapper.props('modelValue').readings).toBe(update.readings)
      }
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero pressure readings', () => {
      const zeroPressureStats = {
        ...samplePressureStats,
        pressure: {
          maxString: '0.000 Bar',
          minString: '0.000 Bar'
        }
      }
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: zeroPressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should handle high pressure values', () => {
      const highPressureStats = {
        ...samplePressureStats,
        pressure: {
          maxString: '4.137 Bar',
          minString: '3.103 Bar'
        }
      }
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: highPressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should handle missing temperature data', () => {
      const incompletePressureStats = {
        ...samplePressureStats,
        temperature: { maxString: '—', minString: '—' }
      }
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: incompletePressureStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should handle many pressure readings', () => {
      const manyReadingStats = {
        ...samplePressureStats,
        readings: 1000
      }
      const wrapper = mount(PressureStatsFragment, {
        props: { modelValue: manyReadingStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })
  })
})
