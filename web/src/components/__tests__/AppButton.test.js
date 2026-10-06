import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppButton from '@/components/AppButton.vue'

describe('AppButton', () => {
  it.each(['primary', 'secondary', 'positive', 'negative', 'warning', 'info', 'outline-primary', 'outline-secondary', 'outline-negative', 'outline-positive'])(
    'applies the shared %s variant', (variant) => {
      const wrapper = mount(AppButton, { props: { variant } })
      expect(wrapper.classes()).toEqual(expect.arrayContaining(['app-button', `app-button--${variant}`]))
      wrapper.unmount()
    }
  )

  it('supports compact buttons and caller layout classes', () => {
    const wrapper = mount(AppButton, { props: { variant: 'primary', dense: true }, attrs: { class: 'app-width-2' } })
    expect(wrapper.classes()).toEqual(expect.arrayContaining(['app-button', 'app-button--primary', 'app-button--dense', 'app-width-2']))
    wrapper.unmount()
  })
})
