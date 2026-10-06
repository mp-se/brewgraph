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

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useBatchNoteStore } from '@/modules/batchNoteStore'

vi.mock('@/ui', async (importActual) => {
  const actual = await importActual()
  return { ...actual, logDebug: vi.fn(), logInfo: vi.fn(), logError: vi.fn() }
})

vi.mock('@/modules/pinia', () => ({
  global: {
    disabled: false,
    acquireBusy() {
      this.disabled = true
      let released = false
      return () => { if (!released) { released = true; this.disabled = false } }
    },
    apiURL: 'http://localhost:8080/api/',
    token: 'Bearer test',
    fetchTimout: 30000
  }
}))

const BATCH_ID = 'batch-001'
const NOTE_ID = 'note-001'

const mockNote = {
  id: NOTE_ID,
  batch_id: BATCH_ID,
  content: 'Test note',
  created_by: 'Magnus',
  created_at: '2026-01-01T10:00:00Z',
  updated_at: '2026-01-01T10:00:00Z'
}

describe('useBatchNoteStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn()
  })

  describe('Initial state', () => {
    it('has empty notes array', () => {
      const store = useBatchNoteStore()
      expect(store.notes).toEqual([])
    })
  })

  describe('getNotes', () => {
    it('fetches notes and populates store', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValueOnce({ items: [mockNote], nextCursor: null, hasMore: false })
      })
      const result = await store.getNotes(BATCH_ID)
      expect(result).toBeTruthy()
      expect(store.notes.length).toBe(1)
      expect(store.notes[0].content).toBe('Test note')
    })

    it('calls correct URL', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValueOnce({ items: [], nextCursor: null, hasMore: false })
      })
      await store.getNotes(BATCH_ID)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`batches/${BATCH_ID}/notes`),
        expect.any(Object)
      )
    })

    it('returns null on network error', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))
      const result = await store.getNotes(BATCH_ID)
      expect(result).toBeNull()
    })

    it('returns null on non-ok response', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 })
      const result = await store.getNotes(BATCH_ID)
      expect(result).toBeNull()
    })
  })

  describe('addNote', () => {
    it('posts content and prepends note to store', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        status: 201,
        ok: true,
        json: vi.fn().mockResolvedValueOnce(mockNote)
      })
      const result = await store.addNote(BATCH_ID, 'Test note')
      expect(result).toBeTruthy()
      expect(store.notes.length).toBe(1)
      expect(store.notes[0].id).toBe(NOTE_ID)
    })

    it('uses unshift so newest note is first', async () => {
      const store = useBatchNoteStore()
      const secondNote = { ...mockNote, id: 'note-002', content: 'Second' }
      global.fetch = vi.fn()
        .mockResolvedValueOnce({ status: 201, ok: true, json: vi.fn().mockResolvedValueOnce(mockNote) })
        .mockResolvedValueOnce({ status: 201, ok: true, json: vi.fn().mockResolvedValueOnce(secondNote) })
      await store.addNote(BATCH_ID, 'First')
      await store.addNote(BATCH_ID, 'Second')
      expect(store.notes[0].id).toBe('note-002')
    })

    it('returns null on non-201 response', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ status: 400, ok: false })
      const result = await store.addNote(BATCH_ID, 'Test note')
      expect(result).toBeNull()
      expect(store.notes.length).toBe(0)
    })

    it('returns null on network error', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('fail'))
      const result = await store.addNote(BATCH_ID, 'Test note')
      expect(result).toBeNull()
    })
  })

  describe('updateNote', () => {
    it('patches and replaces note in store', async () => {
      const store = useBatchNoteStore()
      // Pre-populate
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValueOnce({ items: [mockNote], nextCursor: null, hasMore: false })
      })
      await store.getNotes(BATCH_ID)

      const updated = { ...mockNote, content: 'Updated content' }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValueOnce(updated)
      })
      const result = await store.updateNote(BATCH_ID, NOTE_ID, 'Updated content')
      expect(result).toBe(true)
      expect(store.notes[0].content).toBe('Updated content')
    })

    it('returns false on non-ok response', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
      const result = await store.updateNote(BATCH_ID, NOTE_ID, 'x')
      expect(result).toBe(false)
    })

    it('returns false on network error', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('fail'))
      const result = await store.updateNote(BATCH_ID, NOTE_ID, 'x')
      expect(result).toBe(false)
    })
  })

  describe('deleteNote', () => {
    it('removes note from store on success', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValueOnce({ items: [mockNote], nextCursor: null, hasMore: false })
      })
      await store.getNotes(BATCH_ID)
      expect(store.notes.length).toBe(1)

      global.fetch = vi.fn().mockResolvedValueOnce({ status: 204, ok: true })
      const result = await store.deleteNote(BATCH_ID, NOTE_ID)
      expect(result).toBe(true)
      expect(store.notes.length).toBe(0)
    })

    it('returns false on non-204 response', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockResolvedValueOnce({ status: 500, ok: false })
      const result = await store.deleteNote(BATCH_ID, NOTE_ID)
      expect(result).toBe(false)
    })

    it('returns false on network error', async () => {
      const store = useBatchNoteStore()
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('fail'))
      const result = await store.deleteNote(BATCH_ID, NOTE_ID)
      expect(result).toBe(false)
    })

    it('only removes the targeted note', async () => {
      const store = useBatchNoteStore()
      const note2 = { ...mockNote, id: 'note-002', content: 'Keep me' }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValueOnce({ items: [mockNote, note2], nextCursor: null, hasMore: false })
      })
      await store.getNotes(BATCH_ID)

      global.fetch = vi.fn().mockResolvedValueOnce({ status: 204, ok: true })
      await store.deleteNote(BATCH_ID, NOTE_ID)
      expect(store.notes.length).toBe(1)
      expect(store.notes[0].id).toBe('note-002')
    })
  })
})
