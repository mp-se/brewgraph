import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchEditorActions from '../BatchEditorActions.vue'

function mountActions(props = {}) {
  return mount(BatchEditorActions, {
    props,
    global: {
      stubs: {
        'app-button': {
          props: { variant: String, dense: Boolean },
          template: '<button v-bind="$attrs" :class="[\'app-button\', variant && `app-button--${variant}`, dense && \'app-button--dense\']"><slot /></button>'
        },
        'router-link': { template: '<a><slot /></a>' },
        'q-icon': true,
        BatchBeerXmlImportFragment: true,
        BatchBrewfatherLinkFragment: true
      }
    }
  })
}

describe('BatchEditorActions', () => {
  it('disables save until the batch is changed, named and active', () => {
    const wrapper = mountActions({ batchName: 'Test', hasChanges: false })
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()

    const changed = mountActions({ batchName: 'Test', hasChanges: true })
    expect(changed.find('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(mountActions({ batchName: 'Test', hasChanges: true, isArchived: true })
      .find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('shows lifecycle actions for the current batch state', async () => {
    const wrapper = mountActions({ batchName: 'Test', hasChanges: true })
    await wrapper.get('button[title="Download this batch as a BrewGraph JSON export"]').trigger('click')
    const archiveButton = wrapper.findAll('button').find(button => button.text().trim() === 'Archive')
    await archiveButton.trigger('click')
    expect(wrapper.emitted('export')).toHaveLength(1)
    expect(wrapper.emitted('archive')).toHaveLength(1)

    const archived = mountActions({ batchName: 'Test', isArchived: true })
    const labels = archived.findAll('button').map(button => button.text().trim())
    expect(labels).toContain('Un-archive')
    expect(labels).not.toContain('Archive')
  })

  it('keeps Save and Cancel in the primary group and everything else in the labelled secondary group', () => {
    const wrapper = mountActions({ batchName: 'Test', canFermentationControl: true, batchId: 'b1' })
    const labels = (selector) => wrapper.get(selector).findAll('button').map(b => b.text().trim())
    expect(labels('[data-testid="batch-primary-actions"]')).toEqual(['Save', 'Cancel'])
    const secondary = wrapper.get('[data-testid="batch-secondary-actions"]')
    expect(secondary.text()).toContain('Import, export and status')
    expect(labels('[data-testid="batch-secondary-actions"]')).toEqual(['Export', 'Archive', 'Fermentation Control'])
    expect(secondary.findAll('button').every(b => b.classes().includes('app-button--outline-secondary'))).toBe(true)
    expect(secondary.findComponent({ name: 'BatchBeerXmlImportFragment' }).exists()
      || secondary.html().includes('batch-beer-xml-import-fragment-stub')).toBe(true)
  })
})
