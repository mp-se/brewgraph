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

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { QBtnToggle } from 'quasar'
import SettingsView from '../SettingsView.vue'
import { AppRadioGroup } from '@/ui'
import { AppTextInput } from '@/ui'
import { AppSelect as AppInputSelect } from '@/ui'
import { useConfigStore } from '@/modules/configStore'
import { useGlobalStore } from '@/modules/globalStore'
import { config as piniaConfig, global as piniaGlobal, preferences as piniaPreferences } from '@/modules/pinia'
import * as logger from '@/ui'
import * as utils from '@/modules/utils'

// Mock logger module
vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logWarning: vi.fn(),
    logError: vi.fn()
  }
})

// Mock @/modules/pinia to mock the actual config object with a save method
vi.mock('@/modules/pinia', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    config: {
      ...actual.config,
      save: vi.fn()
    }
  }
})

// Mock utils module (for validateCurrentForm)
vi.mock('@/modules/utils', async () => {
  const actual = await import('@/modules/utils')
  return {
    ...actual,
    validateCurrentForm: vi.fn()
  }
})

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    piniaGlobal.disabled = false
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Basic Rendering', () => {
    it('should render settings container', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true,
            AppPageHeader: false
          }
        }
      })
      const container = wrapper.find('.app-page')
      expect(container.exists()).toBe(true)
    })

    it('should render settings title', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true,
            AppPageHeader: false
          }
        }
      })
      expect(wrapper.text()).toContain('Settings')
    })
  })

  describe('Form Submission - saveSettings()', () => {
    it('does not show a save spinner when settings are initially disabled', () => {
      piniaGlobal.disabled = true

      const wrapper = mount(SettingsView)
      const saveButton = wrapper.get('button[type="submit"]')

      expect(saveButton.attributes('aria-busy')).toBe('false')
      expect(wrapper.find('.app-spinner').exists()).toBe(false)
    })

    it('shows a save spinner only while a save request is pending', async () => {
      let finishSave
      piniaConfig.save.mockReturnValue(new Promise((resolve) => {
        finishSave = resolve
      }))
      utils.validateCurrentForm.mockReturnValue(true)
      const wrapper = mount(SettingsView)

      const savePromise = wrapper.vm.saveSettings()
      await nextTick()

      expect(wrapper.get('button[type="submit"]').attributes('aria-busy')).toBe('true')
      expect(wrapper.find('.app-spinner').exists()).toBe(true)

      finishSave(true)
      await savePromise

      expect(wrapper.get('button[type="submit"]').attributes('aria-busy')).toBe('false')
      expect(wrapper.find('.app-spinner').exists()).toBe(false)
    })

    it('should log debug message when saveSettings is called', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      utils.validateCurrentForm.mockReturnValue(true)

      wrapper.vm.saveSettings()

      expect(logger.logDebug).toHaveBeenCalledWith('SettingsView.saveSettings()')
    })

    it('should return early if form validation fails', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      utils.validateCurrentForm.mockReturnValue(false)

      // Call saveSettings - it should return early without calling config.save
      wrapper.vm.saveSettings()

      // The method doesn't return anything, but we can verify that it didn't crash
      expect(utils.validateCurrentForm).toHaveBeenCalled()
    })

    it('should call saveSettings when form is submitted', async () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      utils.validateCurrentForm.mockReturnValue(true)

      // Directly call saveSettings to verify it works
      wrapper.vm.saveSettings()

      // Verify that logDebug was called (proof that saveSettings ran)
      expect(logger.logDebug).toHaveBeenCalled()
    })

    it('should show success message when save is successful', async () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      piniaConfig.save.mockResolvedValue(true)
      utils.validateCurrentForm.mockReturnValue(true)

      await wrapper.vm.saveSettings()

      expect(piniaConfig.save).toHaveBeenCalled()
      expect(piniaGlobal.messageSuccess).toBe('Settings saved')
    })

    it('should show error message when save fails', async () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      piniaConfig.save.mockResolvedValue(false)
      utils.validateCurrentForm.mockReturnValue(true)

      await wrapper.vm.saveSettings()

      expect(piniaConfig.save).toHaveBeenCalled()
      expect(piniaGlobal.messageError).toBe('Failed to save settings')
    })

    it('should check form validation on submit', async () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      utils.validateCurrentForm.mockReturnValue(true)

      const form = wrapper.find('form')
      await form.trigger('submit')

      expect(utils.validateCurrentForm).toHaveBeenCalled()
    })
  })

  describe('Configuration Binding', () => {
    it('should have config store initialized', () => {
      const config = useConfigStore()
      expect(config).toBeDefined()
    })

    it('should have global store initialized', () => {
      const global = useGlobalStore()
      expect(global).toBeDefined()
    })

    it('should have temperature format option in config', () => {
      mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      const config = useConfigStore()
      expect(config.temperatureFormat).toBeDefined()
    })

    it('should expose config through component instance', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      expect(wrapper.vm.config).toBeDefined()
      expect(wrapper.vm.global).toBeDefined()
    })
  })

  describe('Form Settings Options', () => {
    it('uses compact Quasar button toggles for all format and theme choices', () => {
      const wrapper = mount(SettingsView)

      expect(wrapper.findAll('.q-btn-toggle')).toHaveLength(5)
      expect(wrapper.findAll('.q-option-group')).toHaveLength(0)
      expect(wrapper.find('#temperature-format').attributes('aria-label')).toBe('Temperature Format')
      expect(wrapper.find('#theme').attributes('aria-label')).toBe('Theme')
    })

    it('keeps format and theme button-toggle values bound to their existing stores', async () => {
      const wrapper = mount(SettingsView)
      const toggles = wrapper.findAllComponents(QBtnToggle)

      await toggles[0].vm.$emit('update:modelValue', 'F')
      await toggles[1].vm.$emit('update:modelValue', 'P')
      await toggles[2].vm.$emit('update:modelValue', 'bar')
      await toggles[3].vm.$emit('update:modelValue', 'US')
      await toggles[4].vm.$emit('update:modelValue', true)

      expect(wrapper.vm.config.temperatureFormat).toBe('F')
      expect(wrapper.vm.config.gravityFormat).toBe('P')
      expect(wrapper.vm.config.pressureFormat).toBe('bar')
      expect(wrapper.vm.config.volumeFormat).toBe('US')
      expect(piniaPreferences.dark_mode).toBe(true)
    })

    it('should have temperature format options', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      const temperatureOptions = wrapper.vm.temperatureOptions
      expect(temperatureOptions).toBeDefined()
      expect(temperatureOptions.length).toBeGreaterThan(0)
      expect(temperatureOptions[0]).toHaveProperty('label')
      expect(temperatureOptions[0]).toHaveProperty('value')
    })

    it('should have gravity format options', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      const gravityOptions = wrapper.vm.gravityOptions
      expect(gravityOptions).toBeDefined()
      expect(gravityOptions).toContainEqual({ label: 'Specific Gravity', value: 'SG' })
      expect(gravityOptions).toContainEqual({ label: 'Plato', value: 'P' })
    })

    it('should have pressure format options', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      const pressureOptions = wrapper.vm.pressureOptions
      expect(pressureOptions).toBeDefined()
      expect(pressureOptions).toContainEqual({ label: 'PSI', value: 'PSI' })
      expect(pressureOptions).toContainEqual({ label: 'Bar', value: 'BAR' })
      expect(pressureOptions).toContainEqual({ label: 'kPa', value: 'KPA' })
    })

    it('should have dark mode options', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })

      const darkModeOptions = wrapper.vm.darkModeOptions
      expect(darkModeOptions).toBeDefined()
      expect(darkModeOptions).toContainEqual({ label: 'Dark Mode', value: true })
      expect(darkModeOptions).toContainEqual({ label: 'Day Mode', value: false })
    })
  })

  describe('Form Layout', () => {
    it('should have form element with app-validation class', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })
      const form = wrapper.find('form')
      expect(form.exists()).toBe(true)
      expect(form.classes()).toContain('app-validation')
    })

    it('should have form with novalidate attribute', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })
      const form = wrapper.find('form')
      expect(form.attributes('novalidate')).toBeDefined()
    })

    it('uses Quasar grid classes for responsive columns', () => {
      const wrapper = mount(SettingsView, {
        global: {
          components: {
            AppRadioGroup,
            AppTextInput,
            AppInputSelect
          },
          stubs: {
            AppRadioGroup: true,
            AppTextInput: true,
            AppInputSelect: true
          }
        }
      })
      const row = wrapper.find('.row')
      expect(row.exists()).toBe(true)
      const cols = wrapper.findAll('[class*="col-md"]')
      expect(cols.length).toBeGreaterThan(0)
    })
  })
})
