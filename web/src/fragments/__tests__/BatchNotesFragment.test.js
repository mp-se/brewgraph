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

// deps ../BatchNotesFragment.vue

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchNotesFragment from '../BatchNotesFragment.vue'

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return {
    ...actual,
    logDebug: vi.fn(),
    logInfo: vi.fn(),
    logError: vi.fn()
  }
})

const mockNotes = []
const mockGlobal = { disabled: false, messageError: '' }
const mockBatchNoteStore = {
  notes: mockNotes,
  getNotes: vi.fn().mockResolvedValue([]),
  addNote: vi.fn().mockResolvedValue({ id: 'new-1', content: 'Test note', createdAt: '2026-01-01T00:00:00Z' }),
  updateNote: vi.fn().mockResolvedValue(true),
  deleteNote: vi.fn().mockResolvedValue(true)
}

vi.mock('@/modules/pinia', () => ({
  get global() { return mockGlobal },
  get batchNoteStore() { return mockBatchNoteStore }
}))

const BATCH_ID = 'batch-abc-123'

function mountFragment(overrides = {}) {
  return mount(BatchNotesFragment, {
    props: { batchId: BATCH_ID, ...overrides }
  })
}

describe('BatchNotesFragment', () => {
  beforeEach(() => {
    mockNotes.length = 0
    mockGlobal.disabled = false
    mockGlobal.messageError = ''
    vi.clearAllMocks()
    mockBatchNoteStore.getNotes.mockResolvedValue([])
    mockBatchNoteStore.addNote.mockResolvedValue({ id: 'new-1', content: 'Test note', createdAt: '2026-01-01T00:00:00Z' })
    mockBatchNoteStore.updateNote.mockResolvedValue(true)
    mockBatchNoteStore.deleteNote.mockResolvedValue(true)
  })

  describe('Initial rendering', () => {
    it('renders the Batch Notes label', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Batch Notes')
    })

    it('renders the textarea for new note input', () => {
      const wrapper = mountFragment()
      expect(wrapper.find('textarea').exists()).toBe(true)
    })

    it('renders the Add Note button', () => {
      const wrapper = mountFragment()
      const button = wrapper.findAll('button').find((b) => b.text().includes('Add'))
      expect(button).toBeDefined()
    })

    it('shows empty state when there are no notes', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('No notes yet.')
    })

    it('fetches notes on mount with the correct batchId', async () => {
      mountFragment()
      await Promise.resolve()
      expect(mockBatchNoteStore.getNotes).toHaveBeenCalledWith(BATCH_ID)
    })
  })

  describe('Add Note button state', () => {
    it('is disabled when textarea is empty', () => {
      const wrapper = mountFragment()
      const button = wrapper.find('button')
      expect(button.attributes('disabled')).toBeDefined()
    })

    it('is enabled when textarea has content', async () => {
      const wrapper = mountFragment()
      await wrapper.find('textarea').setValue('hello')
      const button = wrapper.find('button')
      expect(button.attributes('disabled')).toBeUndefined()
    })

    it('is disabled when global.disabled is true', async () => {
      mockGlobal.disabled = true
      const wrapper = mountFragment()
      await wrapper.find('textarea').setValue('hello')
      const button = wrapper.find('button')
      expect(button.attributes('disabled')).toBeDefined()
    })
  })

  describe('Adding a note', () => {
    it('calls addNote with the batchId and trimmed content', async () => {
      const wrapper = mountFragment()
      await wrapper.find('textarea').setValue('  My new note  ')
      await wrapper.find('button').trigger('click')
      expect(mockBatchNoteStore.addNote).toHaveBeenCalledWith(BATCH_ID, 'My new note')
    })

    it('clears the textarea on success', async () => {
      const wrapper = mountFragment()
      await wrapper.find('textarea').setValue('My note')
      await wrapper.find('button').trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.find('textarea').element.value).toBe('')
    })

    it('sets messageError on failure', async () => {
      mockBatchNoteStore.addNote.mockResolvedValue(null)
      const wrapper = mountFragment()
      await wrapper.find('textarea').setValue('My note')
      await wrapper.find('button').trigger('click')
      await wrapper.vm.$nextTick()
      expect(mockGlobal.messageError).toBe('Failed to add note')
    })

    it('does not call addNote for whitespace-only content', async () => {
      const wrapper = mountFragment()
      await wrapper.find('textarea').setValue('   ')
      await wrapper.find('button').trigger('click')
      expect(mockBatchNoteStore.addNote).not.toHaveBeenCalled()
    })
  })

  describe('Rendering existing notes', () => {
    beforeEach(() => {
      mockNotes.push(
        { id: 'note-1', content: 'First note', createdAt: '2026-01-01T10:00:00Z', createdBy: 'Magnus' },
        { id: 'note-2', content: 'Second note', createdAt: '2026-01-02T10:00:00Z', createdBy: '' }
      )
    })

    it('renders a card for each note', () => {
      const wrapper = mountFragment()
      expect(wrapper.findAll('.app-legacy-card').length).toBe(2)
    })

    it('displays note content', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('First note')
      expect(wrapper.text()).toContain('Second note')
    })

    it('displays createdBy when present', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).toContain('Magnus')
    })

    it('renders edit and delete buttons for each note', () => {
      const wrapper = mountFragment()
      expect(wrapper.findAll('.app-button--outline-secondary').length).toBe(2)
      expect(wrapper.findAll('.app-button--outline-negative').length).toBe(2)
    })

    it('does not show empty state when notes exist', () => {
      const wrapper = mountFragment()
      expect(wrapper.text()).not.toContain('No notes yet.')
    })
  })

  describe('Editing a note', () => {
    beforeEach(() => {
      mockNotes.push({ id: 'note-1', content: 'Original content', createdAt: '2026-01-01T10:00:00Z', createdBy: '' })
    })

    it('switches to edit mode when edit button is clicked', async () => {
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-secondary').trigger('click')
      const textareas = wrapper.findAll('textarea')
      expect(textareas.length).toBe(2) // new-note textarea + edit textarea
    })

    it('pre-fills edit textarea with existing content', async () => {
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-secondary').trigger('click')
      const editTextarea = wrapper.findAll('textarea')[1]
      expect(editTextarea.element.value).toBe('Original content')
    })

    it('calls updateNote with correct args on save', async () => {
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-secondary').trigger('click')
      const editTextarea = wrapper.findAll('textarea')[1]
      await editTextarea.setValue('Updated content')
      await wrapper.find('.app-legacy-card .app-button--primary').trigger('click')
      expect(mockBatchNoteStore.updateNote).toHaveBeenCalledWith(BATCH_ID, 'note-1', 'Updated content')
    })

    it('exits edit mode on cancel', async () => {
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-secondary').trigger('click')
      await wrapper.find('.app-legacy-card .app-button--secondary').trigger('click')
      expect(wrapper.findAll('textarea').length).toBe(1)
    })

    it('sets messageError when updateNote fails', async () => {
      mockBatchNoteStore.updateNote.mockResolvedValue(false)
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-secondary').trigger('click')
      const editTextarea = wrapper.findAll('textarea')[1]
      await editTextarea.setValue('Updated content')
      await wrapper.find('.app-legacy-card .app-button--primary').trigger('click')
      await wrapper.vm.$nextTick()
      expect(mockGlobal.messageError).toBe('Failed to update note')
    })
  })

  describe('Deleting a note', () => {
    beforeEach(() => {
      mockNotes.push({ id: 'note-1', content: 'To be deleted', createdAt: '2026-01-01T10:00:00Z', createdBy: '' })
    })

    it('calls deleteNote with batchId and noteId', async () => {
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-negative').trigger('click')
      expect(mockBatchNoteStore.deleteNote).toHaveBeenCalledWith(BATCH_ID, 'note-1')
    })

    it('sets messageError when deleteNote fails', async () => {
      mockBatchNoteStore.deleteNote.mockResolvedValue(false)
      const wrapper = mountFragment()
      await wrapper.find('.app-button--outline-negative').trigger('click')
      await wrapper.vm.$nextTick()
      expect(mockGlobal.messageError).toBe('Failed to delete note')
    })
  })

  describe('formatDate helper', () => {
    beforeEach(() => {
      mockNotes.push({ id: 'note-1', content: 'Note', createdAt: '2026-06-10T12:00:00Z', createdBy: '' })
    })

    it('renders a human-readable date string', () => {
      const wrapper = mountFragment()
      const small = wrapper.find('small')
      expect(small.text()).not.toBe('')
      expect(small.text()).not.toBe('2026-06-10T12:00:00Z')
    })
  })

  describe('Disabled state', () => {
    beforeEach(() => {
      mockGlobal.disabled = true
      mockNotes.push({ id: 'note-1', content: 'A note', createdAt: '2026-01-01T10:00:00Z', createdBy: '' })
    })

    it('disables the new-note textarea', () => {
      const wrapper = mountFragment()
      expect(wrapper.find('textarea').attributes('disabled')).toBeDefined()
    })

    it('disables edit and delete buttons', () => {
      const wrapper = mountFragment()
      wrapper.findAll('.app-button--outline-secondary').forEach((button) => {
        expect(button.attributes('disabled')).toBeDefined()
      })
      wrapper.findAll('.app-button--outline-negative').forEach((button) => {
        expect(button.attributes('disabled')).toBeDefined()
      })
    })
  })
})
