<!--
  Copyright (c) 2024-2026 Magnus Persson
  SPDX-License-Identifier: GPL-3.0-only
  BrewGraph — https://github.com/mp-se/brewgraph

  This file is part of BrewGraph. For open source use it is licensed under
  the GNU General Public License v3.0. For commercial use without source
  disclosure, a separate Commercial License is required.
  See LICENSE for details.
-->

<template>
  <div>
    <div class="row justify-between items-center q-mb-sm">
      <label class="app-field-label text-weight-bold q-mb-none">Batch Notes</label>
    </div>

    <!-- Add note form -->
    <div class="q-mb-md">
      <textarea
        v-model="newContent"
        class="app-native-input"
        rows="3"
        placeholder="Add a note…"
        maxlength="5000"
        :disabled="disabled"
      ></textarea>
      <div class="q-mt-xs row justify-end">
        <app-button
          type="button"
          variant="outline-primary" dense
          :disabled="disabled || !newContent.trim()"
          @click="addNote"
        >
          <q-icon name="add_circle" /> Add
        </app-button>
      </div>
    </div>

    <!-- Note list -->
    <div v-if="batchNoteStore.notes.length === 0" class="text-grey-7">
      No notes yet.
    </div>

    <div v-for="note in batchNoteStore.notes" :key="note.id" class="app-legacy-card q-mb-sm">
      <div class="app-legacy-card__body q-py-sm q-px-md">
        <template v-if="editingId === note.id">
          <textarea
            v-model="editContent"
            class="app-native-input app-native-input--dense q-mb-sm"
            rows="3"
            maxlength="5000"
            :disabled="disabled"
          ></textarea>
          <div class="row q-gutter-sm">
            <app-button
              type="button"
              variant="primary" dense
              :disabled="disabled || !editContent.trim()"
              @click="saveEdit(note)"
            >
              <q-icon name="save" /> Save
            </app-button>
            <app-button
              type="button"
              variant="secondary" dense
              :disabled="disabled"
              @click="cancelEdit"
            >
              Cancel
            </app-button>
          </div>
        </template>

        <template v-else>
          <p class="q-mb-xs" style="white-space: pre-wrap">{{ note.content }}</p>
          <div class="row justify-between items-center">
            <small class="text-grey-7">{{ formatDate(note.createdAt) }}<template v-if="note.createdBy"> · {{ note.createdBy }}</template></small>
            <div class="row q-gutter-xs">
              <app-button
                type="button"
                variant="outline-secondary" dense
                :disabled="disabled"
                @click="startEdit(note)"
               aria-label="Edit note">
                <q-icon name="edit" />
              </app-button>
              <app-button
                type="button"
                variant="outline-negative" dense
                :disabled="disabled"
                @click="deleteNote(note.id)"
               aria-label="Delete note">
                <q-icon name="delete" />
              </app-button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { global, batchNoteStore } from '@/modules/pinia'
import { logDebug } from '@/ui'

interface NoteShape { id: string; content: string }

const props = defineProps<{ batchId: string; readOnly?: boolean }>()
const disabled = computed(() => global.disabled || !!props.readOnly)

onMounted(() => batchNoteStore.getNotes(props.batchId))

const newContent = ref('')
const editingId = ref<string | null>(null)
const editContent = ref('')

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function addNote() {
  logDebug('BatchNotes.addNote()')
  const trimmed = newContent.value.trim()
  if (!trimmed) return
  const result = await batchNoteStore.addNote(props.batchId, trimmed)
  if (result) {
    newContent.value = ''
  } else {
    global.messageError = 'Failed to add note'
  }
}

function startEdit(note: NoteShape) {
  editingId.value = note.id
  editContent.value = note.content
}

function cancelEdit() {
  editingId.value = null
  editContent.value = ''
}

async function saveEdit(note: NoteShape) {
  logDebug('BatchNotes.saveEdit()', note.id)
  const trimmed = editContent.value.trim()
  if (!trimmed) return
  const ok = await batchNoteStore.updateNote(props.batchId, note.id, trimmed)
  if (ok) {
    cancelEdit()
  } else {
    global.messageError = 'Failed to update note'
  }
}

async function deleteNote(noteId: string) {
  logDebug('BatchNotes.deleteNote()', noteId)
  const ok = await batchNoteStore.deleteNote(props.batchId, noteId)
  if (!ok) global.messageError = 'Failed to delete note'
}

</script>
