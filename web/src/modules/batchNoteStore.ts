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

import { defineStore } from 'pinia'
import { logDebug } from '@/ui'
import { BatchNote } from '@/modules/classes'
import { apiJson, apiOk } from '@/modules/apiClient'
import type { PiniaModel } from '@/modules/piniaModel'

type StoredBatchNote = PiniaModel<BatchNote>

export const useBatchNoteStore = defineStore('batchNoteStore', {
  state: () => ({
    notes: [] as StoredBatchNote[]
  }),
  actions: {
    async getNotes(batchId: string): Promise<StoredBatchNote[] | null> {
      logDebug('batchNoteStore.getNotes()', batchId)
      // Cursor-paginated; the note list is short enough that the first page is the
      // whole story in practice, and `hasMore` is there when it is not.
      const json = await apiJson<{ items: Record<string, unknown>[] }>(
        'GET',
        `batches/${batchId}/notes`
      )
      if (!json) return null
      this.notes = (json.items ?? []).map((n) => BatchNote.fromJson(n))
      return this.notes
    },

    async addNote(batchId: string, content: string): Promise<BatchNote | null> {
      logDebug('batchNoteStore.addNote()', batchId)
      const json = await apiJson<Record<string, unknown>>(
        'POST',
        `batches/${batchId}/notes`,
        { content },
        { okStatuses: [201] }
      )
      if (!json) return null
      const note = BatchNote.fromJson(json)
      this.notes.unshift(note)
      return note
    },

    async updateNote(batchId: string, noteId: string, content: string): Promise<boolean> {
      logDebug('batchNoteStore.updateNote()', noteId)
      const json = await apiJson<Record<string, unknown>>(
        'PATCH',
        `batches/${batchId}/notes/${noteId}`,
        { content }
      )
      if (!json) return false
      const updated = BatchNote.fromJson(json)
      const idx = this.notes.findIndex((n) => n.id === noteId)
      if (idx !== -1) this.notes.splice(idx, 1, updated)
      return true
    },

    async deleteNote(batchId: string, noteId: string): Promise<boolean> {
      logDebug('batchNoteStore.deleteNote()', noteId)
      const ok = await apiOk('DELETE', `batches/${batchId}/notes/${noteId}`, undefined, {
        okStatuses: [204]
      })
      if (ok) this.notes = this.notes.filter((n) => n.id !== noteId)
      return ok
    }
  }
})
