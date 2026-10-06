import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchDryHopsFragment from '../BatchDryHopsFragment.vue'

const mocks = vi.hoisted(() => ({
  global: { disabled: false, messageError: '' },
  apiJson: vi.fn().mockResolvedValue({ dryHops: [] }),
  apiOk: vi.fn().mockResolvedValue(true)
}))

vi.mock('@/modules/pinia', () => ({ global: mocks.global }))
vi.mock('@/modules/apiClient', () => ({ apiJson: mocks.apiJson, apiOk: mocks.apiOk }))
vi.mock('bootstrap', () => ({
  Modal: class {
    static getInstance() { return { hide: vi.fn() } }
    show = vi.fn()
  }
}))

function mountFragment() {
  return mount(BatchDryHopsFragment, {
    props: { batchId: 'batch-1' },
    global: { stubs: { AppTextInput: { template: '<input required />' }, AppInputNumber: true } }
  })
}

describe('BatchDryHopsFragment add modal', () => {
  it('marks hop name required and disables Add when blank', async () => {
    const wrapper = mountFragment()
    const nameInput = wrapper.find('input[required]')
    const addButton = wrapper.find('button.bg-primary')

    expect(nameInput.attributes('required')).toBeDefined()
    expect(addButton.attributes('disabled')).toBeDefined()

    wrapper.vm.newHop.name = '   '
    await wrapper.vm.$nextTick()
    expect(addButton.attributes('disabled')).toBeDefined()
  })

  it('does not submit a whitespace-only hop name', async () => {
    const wrapper = mountFragment()
    wrapper.vm.newHop.name = '   '

    await wrapper.vm.addDryHop()

    expect(mocks.apiOk).not.toHaveBeenCalled()
  })

  it('trims a submitted hop name', async () => {
    const wrapper = mountFragment()
    wrapper.vm.newHop.name = '  Citra  '

    await wrapper.vm.addDryHop()

    expect(mocks.apiOk).toHaveBeenCalledWith('POST', 'batches/batch-1/dry-hops', [
      expect.objectContaining({ name: 'Citra' })
    ])
  })
})
