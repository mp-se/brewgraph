/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

// deps ../deviceSetup.ts

import { describe, it, expect } from 'vitest'
import { deviceSetupFor } from '../deviceSetup'
import { deviceTypeOptions } from '../classes'

describe('deviceSetupFor', () => {
  it('has instructions for every device type that can be selected', () => {
    const missing = deviceTypeOptions
      .filter(({ value }) => value !== '' && deviceSetupFor(value) === null)
      .map(({ label }) => label)
    expect(missing).toEqual([])
  })

  it.each([
    ['ispindel', '/ingest/ispindel'],
    ['gravitymon', '/ingest/gravitymon'],
    ['gravitymon_gateway', '/ingest/gravitymon'],
    ['pressuremon', '/ingest/pressuremon'],
    ['kegmon', '/ingest/kegmon'],
    ['chamber_controller', '/ingest/chamber']
  ])('%s posts to %s', (type, path) => {
    expect(deviceSetupFor(type)?.path).toBe(path)
  })

  it('only the iSpindel asks for separate address fields', () => {
    expect(deviceSetupFor('ispindel')?.separateFields).toBe(true)
    expect(deviceSetupFor('gravitymon')?.separateFields).toBeFalsy()
  })

  it.each(['', null, undefined, 'something-else'])('returns null for %j', (type) => {
    expect(deviceSetupFor(type)).toBeNull()
  })
})
