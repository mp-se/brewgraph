import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { Quasar } from 'quasar'
const chartConfigs = vi.hoisted(() => [] as { data: { datasets: { label: string; borderWidth?: number }[] } }[])
vi.mock('chart.js', () => ({
  Chart: class { static register() {} constructor(_canvas: unknown, config: never) { chartConfigs.push(config) } destroy() {} },
  registerables: []
}))
import GravityFormulaEditor from '../GravityFormulaEditor.vue'

const props = {
  formula: null,
  unit: 'sg' as const,
  points: [] as { angle: number; gravity: number }[],
  deviceName: 'Tilt One',
  deviceType: 'gravitymon',
}

function editor(overrides = {}) {
  return mount(GravityFormulaEditor, { props: { ...props, ...overrides }, global: { plugins: [Quasar] } })
}

type EditorVm = {
  setFormula: (formula: string) => void
  addPoint: () => void
  rows: { angle: string; gravity: string }[]
  commitRows: () => void
  candidates: unknown[]
  importProfile: (event: Event) => Promise<void>
  profileErrors: string[]
}

const vm = (wrapper: ReturnType<typeof editor>) => wrapper.vm as unknown as EditorVm

describe('GravityFormulaEditor', () => {
  it('opens on the table when no points are entered and on the formula when there are some', () => {
    expect(editor().text()).toContain('Add point')
    expect(editor().text()).not.toContain('Fit candidates')
    const withPoints = editor({ points: [{ angle: 20, gravity: 1.02 }] })
    expect(withPoints.text()).toContain('Fit candidates')
  })

  it('replaces the current formula with a fitted candidate at once', async () => {
    const points = [{ angle: 20, gravity: 1.01 }, { angle: 30, gravity: 1.02 }, { angle: 40, gravity: 1.04 }]
    const wrapper = editor({ points, formula: 'tilt' })
    await wrapper.find('[aria-label="Use degree 1 formula"]').trigger('click')
    const emitted = wrapper.emitted('update:formula') ?? []
    const latest = emitted[emitted.length - 1]?.[0] as string
    expect(latest).not.toBe('tilt')
    expect(latest).toContain('tilt')
  })

  it('reports a copied formula to the page', async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
    const wrapper = editor({ points: [{ angle: 20, gravity: 1.02 }], formula: 'tilt' })
    await (wrapper.vm as unknown as { copyFormula: () => Promise<void> }).copyFormula()
    expect(wrapper.emitted('copied')).toHaveLength(1)
  })

  it('draws every fitted formula on the graph and marks the selected one', async () => {
    const points = [{ angle: 20, gravity: 1.01 }, { angle: 30, gravity: 1.02 }, { angle: 40, gravity: 1.04 },
      { angle: 50, gravity: 1.07 }, { angle: 60, gravity: 1.11 }]
    const wrapper = editor({ points, formula: 'tilt' })
    const inner = wrapper.vm as unknown as { view: string; candidates: { degree: number; formula: string }[] }
    const degree2 = inner.candidates[1].formula
    await wrapper.setProps({ formula: degree2 })
    inner.view = 'graph'
    await wrapper.vm.$nextTick(); await wrapper.vm.$nextTick(); await flushPromises()
    const labels = chartConfigs[chartConfigs.length - 1].data.datasets.map(set => set.label)
    expect(labels).toEqual(expect.arrayContaining(['Calibration points', 'Degree 1', 'Degree 2 (selected)', 'Degree 3', 'Degree 4']))
    expect(labels).not.toContain('Selected formula')

    await wrapper.setProps({ formula: '1+tilt/1000' })
    await wrapper.vm.$nextTick(); await wrapper.vm.$nextTick(); await flushPromises()
    const again = chartConfigs[chartConfigs.length - 1].data.datasets.map(set => set.label)
    expect(again).toContain('Selected formula')
    expect(again).toContain('Degree 2')
  })

  it('offers Copy formula only on the Formula view and leaves import and export to the page', async () => {
    const wrapper = editor({ points: [{ angle: 20, gravity: 1.02 }], formula: 'tilt' })
    expect(wrapper.text()).toContain('Copy formula')
    expect(wrapper.text()).not.toContain('Import profile')
    expect(wrapper.text()).not.toContain('Export profile')
    ;(wrapper.vm as unknown as { view: string }).view = 'table'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('Copy formula')
  })

  it('enters values in the app gravity unit and words the limits in it', async () => {
    for (const [displayUnit, limits] of [['sg', '0.980 and 1.250 SG'], ['plato', '-5.26 and 52.88 °P']] as const) {
      const wrapper = editor({ points: [{ angle: 20, gravity: 1.02 }], formula: 'tilt', displayUnit })
      const inner = wrapper.vm as unknown as { view: string; rows: { gravity: string }[]; rowErrors: { gravity?: string }[] }
      inner.view = 'table'
      inner.rows[0].gravity = '9999'
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).not.toContain('Gravity unit')
      expect(inner.rowErrors[0].gravity).toBe('Gravity must be between ' + limits)
    }
  })

  it('shows stored points rounded in the app unit', () => {
    const wrapper = editor({ points: [{ angle: 20, gravity: 1.0429 }], displayUnit: 'plato' })
    const inner = wrapper.vm as unknown as { rows: { gravity: string }[] }
    expect(inner.rows[0].gravity).toBe('10.692')
  })

  it('reports the test result and graph axis in the unit the formula returns', async () => {
    const wrapper = editor({ points: [{ angle: 20, gravity: 1.02 }], formula: '10', unit: 'plato', deviceType: 'ispindel' })
    const inner = wrapper.vm as unknown as { testResult: string }
    expect(inner.testResult).toBe('Result: 10.00 °P')
  })

  it('starts at the user\'s gravity preference and saves the first formula with an explicit unit', async () => {
    const wrapper = editor({ displayUnit: 'plato', unit: 'sg', formula: null })
    const inner = wrapper.vm as unknown as { effectiveUnit: string; setFormula: (v: string) => void }
    expect(inner.effectiveUnit).toBe('plato')
    inner.setFormula('tilt')
    expect(wrapper.emitted('update:unit')?.[0]).toEqual(['plato'])
  })

  it('keeps the unit a saved formula was stored with whatever the preference is', () => {
    const wrapper = editor({ displayUnit: 'plato', unit: 'sg', formula: 'tilt' })
    expect((wrapper.vm as unknown as { effectiveUnit: string }).effectiveUnit).toBe('sg')
  })

  it('exposes the actions the page buttons call', () => {
    const wrapper = editor()
    const exposed = wrapper.vm as unknown as { openImport: () => void; exportProfile: () => void }
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    const click = vi.spyOn(input, 'click')
    exposed.openImport()
    expect(click).toHaveBeenCalled()
    expect(typeof exposed.exportProfile).toBe('function')
  })

  it('shows the save notice without disabling the editor', () => {
    const wrapper = editor({ points: [{ angle: 20, gravity: 1.02 }] })
    expect(wrapper.text()).toContain('does not change the formula on the device')
    expect(wrapper.text()).toContain('Fit candidates')
  })

  it('emits formula changes and rejects invalid syntax', async () => {
    const wrapper = editor()
    vm(wrapper).setFormula('1+tilt/1000')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:formula')?.[0]).toEqual(['1+tilt/1000'])
    vm(wrapper).setFormula('1+constructor')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('valid')?.slice(-1)[0]).toEqual([false])
  })

  it('keeps invalid rows local and commits only valid SG points', async () => {
    const wrapper = editor()
    vm(wrapper).addPoint()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('valid')?.slice(-1)[0]).toEqual([false])
    vm(wrapper).rows[0].angle = '30'
    vm(wrapper).rows[0].gravity = '1.03'
    vm(wrapper).commitRows()
    await flushPromises()
    expect(wrapper.emitted('update:points')?.slice(-1)[0]).toEqual([[{ angle: 30, gravity: 1.03 }]])
  })

  it('shows four fit candidates and validates the import before applying it', async () => {
    const wrapper = editor({ points: [{ angle: 20, gravity: 1.02 }, { angle: 40, gravity: 1.04 }] })
    expect(vm(wrapper).candidates).toHaveLength(4)
    const bad = { format: 'wrong', version: 2, gravityFormula: 'constructor',
      gravityFormulaUnit: 'plato', gravityCalibrationData: [{ angle: 20, gravity: 2 }] }
    const file = { text: vi.fn().mockResolvedValue(JSON.stringify(bad)) }
    await vm(wrapper).importProfile({ target: { files: [file], value: 'profile.json' } } as unknown as Event)
    expect(vm(wrapper).profileErrors.length).toBeGreaterThan(1)
    expect(wrapper.emitted('update:formula')).toBeUndefined()
  })
})
