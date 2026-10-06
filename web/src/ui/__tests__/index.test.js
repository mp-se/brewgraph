import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { QBtn, QSelect } from 'quasar'
import { nextTick } from 'vue'
import { AppCard, AppInputNumber, AppRadioGroup, AppDataDialog, AppConfirmDialog, AppSelectDialog, AppToggle } from '../index'

describe('Quasar compatibility controls', () => {
  it('keeps the legacy dialog component contracts registered', () => {
    expect(AppDataDialog.name).toBe('AppDataDialog')
    expect(AppConfirmDialog.name).toBe('AppConfirmDialog')
    expect(AppSelectDialog.name).toBe('AppSelectDialog')
  })

  it('starts select dialogs with no selection instead of Vue Boolean default false', async () => {
    const wrapper = mount(AppSelectDialog, {
      props: { options: [{ label: 'Batch 1', value: 'batch-1' }] }
    })

    await wrapper.find('button').trigger('click')
    await nextTick()
    expect(wrapper.findComponent(QSelect).props('modelValue')).toBeNull()
  })

  it('preserves an explicitly supplied false select-dialog value', async () => {
    const wrapper = mount(AppSelectDialog, { props: { modelValue: false } })

    await wrapper.find('button').trigger('click')
    await nextTick()
    expect(wrapper.findComponent(QSelect).props('modelValue')).toBe(false)
  })

  it('does not let a select dialog confirm until something is selected', async () => {
    const wrapper = mount(AppSelectDialog, {
      props: { options: [{ label: '- none -', value: '' }, { label: 'Device 1', value: 'd1' }] }
    })
    await wrapper.find('button').trigger('click')
    await nextTick()
    const confirm = () => wrapper.findAllComponents(QBtn).find((b) => b.props('label') === 'Confirm')

    expect(confirm().props('disable')).toBe(true) // nothing chosen yet

    wrapper.findComponent(QSelect).vm.$emit('update:modelValue', '')
    await nextTick()
    expect(confirm().props('disable')).toBe(true) // the '- none -' entry is not a choice

    wrapper.findComponent(QSelect).vm.$emit('update:modelValue', 'd1')
    await nextTick()
    expect(confirm().props('disable')).toBe(false)
  })

  it('emits numeric values from number inputs', async () => {
    const wrapper = mount(AppInputNumber)
    await wrapper.find('input').setValue('12.5')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([12.5])
  })

  it('maps an empty nullable number input to null', async () => {
    const wrapper = mount(AppInputNumber, { props: { nullable: true, modelValue: 12.5 } })
    await wrapper.find('input').setValue('')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([null])
  })

  it('keeps non-nullable empty number input behavior unchanged', async () => {
    const wrapper = mount(AppInputNumber, { props: { modelValue: 12.5 } })
    await wrapper.find('input').setValue('')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([''])
  })

  it('uses scalar radio controls for legacy radio fields', () => {
    const wrapper = mount(AppRadioGroup, {
      props: { modelValue: 'sg', options: [{ label: 'SG', value: 'sg' }] }
    })
    expect(wrapper.find('.q-radio').exists()).toBe(true)
    expect(wrapper.find('.q-toggle').exists()).toBe(false)
  })

  it('shows a toggle label once, as the header, and keeps it as the accessible name', () => {
    const wrapper = mount(AppToggle, { props: { modelValue: true, label: 'Accepting' } })
    expect(wrapper.text().match(/Accepting/g)).toHaveLength(1)
    expect(wrapper.find('.app-field-label').text()).toBe('Accepting')
    expect(wrapper.find('.q-toggle__label').exists()).toBe(false)
    expect(wrapper.find('[role="switch"]').attributes('aria-label')).toBe('Accepting')
  })

  it('supports an inline toggle label for compact status rows', () => {
    const wrapper = mount(AppToggle, { props: { modelValue: true, label: 'Enabled', inline: true } })
    expect(wrapper.find('.app-field-label').exists()).toBe(false)
    expect(wrapper.find('.q-toggle__label').text()).toBe('Enabled')
    expect(wrapper.find('[role="switch"]').attributes('aria-label')).toBe('Enabled')
  })

  it('lets a caller-supplied aria-label replace the default toggle name', () => {
    const wrapper = mount(AppToggle, {
      props: { modelValue: false, label: 'Data' },
      attrs: { 'aria-label': 'Show only batches with data' }
    })
    expect(wrapper.find('[role="switch"]').attributes('aria-label')).toBe('Show only batches with data')
  })

  it('renders semantic, accented card headers', () => {
    const wrapper = mount(AppCard, { props: { header: 'On tap', color: 'success' } })
    const header = wrapper.find('.app-card__header')

    expect(header.text()).toBe('On tap')
    expect(header.classes()).toContain('app-card__header--success')
    expect(wrapper.classes()).toContain('app-card--success')
  })
})
