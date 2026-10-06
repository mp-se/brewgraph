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

import { logDebug } from '@/ui'
import { config, deviceStore } from '@/modules/pinia'
import {
  fermentationStepsPayload as coreFermentationStepsPayload,
  hasActiveFermentationStepAt,
  parseFermentationStepsForEditor as coreParseFermentationStepsForEditor,
  serializeFermentationSteps as coreSerializeFermentationSteps,
  stepsInCelsius as coreStepsInCelsius,
  type EditorFermentationStep
} from '@brewgraph/core'

export type { EditorFermentationStep }

/**
 * Parse stored fermentation steps (JSON string or array) into editor rows.
 * Temperatures are converted C→F for display when the UI is set to Fahrenheit.
 */
export function parseFermentationStepsForEditor(stepsRaw: unknown): EditorFermentationStep[] {
  return coreParseFermentationStepsForEditor(stepsRaw, { usesFahrenheit: config.isTempF })
}

/** Convert editor temperatures back to Celsius (database always stores Celsius). */
export function stepsInCelsius(steps: EditorFermentationStep[]): EditorFermentationStep[] {
  return coreStepsInCelsius(steps, { usesFahrenheit: config.isTempF })
}

/** Serialize editor rows to the JSON string stored on the batch ('' when empty). */
export function serializeFermentationSteps(steps: EditorFermentationStep[]): string {
  return coreSerializeFermentationSteps(steps, { usesFahrenheit: config.isTempF })
}

/** Build the API payload for the batch's fermentation steps. */
export function fermentationStepsPayload(batchId: string, steps: EditorFermentationStep[]) {
  const payload = coreFermentationStepsPayload(batchId, steps, { usesFahrenheit: config.isTempF })
  logDebug('fermentationStepEditor.fermentationStepsPayload()', JSON.stringify(payload))
  return payload
}

/** Replace the batch's stored fermentation steps with the editor rows. */
export async function persistFermentationSteps(
  batchId: string,
  steps: EditorFermentationStep[]
): Promise<boolean> {
  logDebug('fermentationStepEditor.persistFermentationSteps()', batchId, 'steps:', steps.length)
  const deleted = await deviceStore.deleteFermentationSteps(batchId)
  logDebug('fermentationStepEditor.persistFermentationSteps()', 'deleted:', deleted)
  if (!deleted) return false

  const payload = fermentationStepsPayload(batchId, steps)
  if (payload.length === 0) {
    logDebug('fermentationStepEditor.persistFermentationSteps()', 'no steps to save')
    return true
  }

  const result = await deviceStore.addFermentationSteps(batchId, payload)
  logDebug('fermentationStepEditor.persistFermentationSteps()', 'addFermentationSteps result:', result)
  return result
}

/** True when any step's date window includes today. */
export function hasActiveFermentationStepNow(steps: unknown): boolean {
  return hasActiveFermentationStepAt(steps)
}
