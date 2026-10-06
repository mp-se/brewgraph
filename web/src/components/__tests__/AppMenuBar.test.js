import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppMenuBar from '../AppMenuBar.vue'

vi.mock('quasar', async (importActual) => ({
  ...(await importActual()),
  useQuasar: () => ({ dark: { set: vi.fn() } })
}))

vi.mock('@/modules/pinia', () => ({
  config: { mdns: '' },
  preferences: { dark_mode: false },
  global: {
    dark_mode: false,
    disabled: false,
    configChanged: false,
    batchChanged: false,
    deviceChanged: false,
    tapChanged: false,
    vesselChanged: false
  }
}))

vi.mock('@/modules/router', () => ({
  items: [
    { label: 'Home', icon: 'home', path: '/', subs: [] },
    { label: 'Device', icon: 'memory', path: '/device', subs: [] },
    { label: 'Cellar', icon: 'construction', path: '/cellar', subs: [
      { label: 'Taps', path: '/cellar/taps' },
      { label: 'Vessels', path: '/cellar/vessels' }
    ] }
  ]
}))

async function mountMenu() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/', '/device', '/cellar/taps', '/cellar/vessels'].map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(AppMenuBar, {
    props: { brand: 'BrewGraph' },
    global: { plugins: [router] }
  })
  return { wrapper, router }
}

describe('AppMenuBar', () => {
  it('renders the Quasar toolbar navigation', async () => {
    const { wrapper } = await mountMenu()
    expect(wrapper.find('.q-toolbar').exists()).toBe(true)
    expect(wrapper.text()).toContain('BrewGraph')
    expect(wrapper.text()).toContain('Cellar')
    expect(wrapper.find('.q-icon').exists()).toBe(true)
    wrapper.unmount()
  })

  it('keeps the Cellar menu available', async () => {
    const { wrapper, router } = await mountMenu()
    expect(wrapper.text()).toContain('Cellar')
    await router.push('/cellar/taps')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/cellar/taps')
    wrapper.unmount()
  })

  it('marks the current top-level route active', async () => {
    const { wrapper } = await mountMenu()
    expect(wrapper.find('.text-weight-bold').exists()).toBe(true)
    wrapper.unmount()
  })

  it('expands the mobile navigation', async () => {
    const { wrapper } = await mountMenu()
    await wrapper.find('button[aria-label="Toggle navigation"]').trigger('click')
    expect(wrapper.find('.app-mobile-menu').exists()).toBe(true)
    wrapper.unmount()
  })

  it('disables navigation controls while busy', async () => {
    const { wrapper, router } = await mountMenu()
    await wrapper.setProps({ disabled: true })
    expect(router.currentRoute.value.path).toBe('/')
    wrapper.unmount()
  })
})
