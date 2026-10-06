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
import GravityStatsFragment from '../GravityStatsFragment.vue'
import { AppReadonlyInput } from '@/ui'
import { AppField } from '@/ui'

describe('GravityStatsFragment - Gravity Statistics Display', () => {
  const sampleGravityStats = {
    gravity: {
      maxString: '1.050 SG',
      minString: '1.010 SG'
    },
    abvString: '5.2%',
    readings: 15,
    averageIntervalString: '1.2 days',
    temperature: {
      maxString: '22.00 C',
      minString: '20.00 C'
    },
    date: {
      firstDate: '2024-01-15',
      lastDate: '2024-01-30'
    }
  }

  describe('Basic Rendering', () => {
    it('should render when gravityStats is provided', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(true)
    })

    it('should not render when gravityStats is null', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: null },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(false)
    })

    it('should have row class for layout', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(true)
    })
  })

  describe('Display Fields', () => {
    it('should display OG (Original Gravity)', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('OG')
    })

    it('should display FG (Final Gravity)', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('FG')
    })

    it('should display ABV (Alcohol by Volume)', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('ABV')
    })

    it('should display reading count', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Readings')
    })

    it('should display average interval', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Avg interval')
    })

    it('should display high and low temperatures', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.text()).toContain('Temp min')
      expect(wrapper.text()).toContain('Temp max')
    })

    it('should display first and last dates', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
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
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })

      expect(wrapper.find('.row').exists()).toBe(true)

      await wrapper.setProps({ modelValue: null })
      expect(wrapper.find('.row').exists()).toBe(false)

      await wrapper.setProps({ modelValue: sampleGravityStats })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should preserve model state through prop updates', async () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })

      const updates = [
        { ...sampleGravityStats, readings: 20 },
        { ...sampleGravityStats, readings: 25 },
        { ...sampleGravityStats, readings: 30 }
      ]

      for (const update of updates) {
        await wrapper.setProps({ modelValue: update })
        expect(wrapper.props('modelValue').readings).toBe(update.readings)
      }
    })
  })

  describe('Edge Cases', () => {
    it('should handle missing temperature data', () => {
      const incompleteStats = {
        ...sampleGravityStats,
        temperature: { maxString: '—', minString: '—' }
      }
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: incompleteStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should handle zero readings', () => {
      const zeroReadingsStats = {
        ...sampleGravityStats,
        readings: 0
      }
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: zeroReadingsStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should handle very high gravity values', () => {
      const highGravityStats = {
        ...sampleGravityStats,
        gravity: {
          maxString: '1.120 SG',
          minString: '1.020 SG'
        }
      }
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: highGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })
  })

  describe('Component Structure - Branch Coverage', () => {
    it('should conditionally render based on gravityStats being null', () => {
      const wrapperWithData = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const wrapperWithNull = mount(GravityStatsFragment, {
        props: { modelValue: null },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapperWithData.find('.row').exists()).toBe(true)
      expect(wrapperWithNull.find('.row').exists()).toBe(false)
    })

    it('should render outer wrapper', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      expect(wrapper.find('.row').exists()).toBe(true)
    })

    it('should have row div', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(true)
    })

    it('should render each field in appropriate column widths', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const colMd2 = wrapper.findAll('.col-md-2')
      expect(colMd2.length).toBeGreaterThanOrEqual(9)
    })

    it('should pass correct label props to all inputs', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const inputs = wrapper.findAllComponents(AppReadonlyInput)
      const labels = inputs.map((input) => input.props('label'))
      expect(labels).toContain('OG')
      expect(labels).toContain('FG')
      expect(labels).toContain('ABV')
      expect(labels).toContain('Readings')
      expect(labels).toContain('Avg interval')
      expect(labels).toContain('Temp min')
      expect(labels).toContain('Temp max')
      expect(labels).toContain('First')
      expect(labels).toContain('Last')
    })

    it('should render each AppReadonlyInput with value binding', () => {
      const wrapper = mount(GravityStatsFragment, {
        props: { modelValue: sampleGravityStats },
        global: {
          components: { AppReadonlyInput, AppField }
        }
      })
      const inputs = wrapper.findAllComponents(AppReadonlyInput)
      expect(inputs.length).toBeGreaterThan(0)
      // OG is first - verify the label prop is passed correctly
      expect(inputs[0].props('label')).toBe('OG')
    })
  })
})
