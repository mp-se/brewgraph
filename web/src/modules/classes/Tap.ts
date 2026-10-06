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

interface TapParams {
  id?: string
  name?: string
  tapNumber?: number | null
  glassSize?: number | null
  location?: string
  notes?: string
  token?: string
  createdAt?: string
  updatedAt?: string
  lastCleanedAt?: string
  vesselName?: string | null
  volumeRemaining?: number | null
  batchName?: string | null
  batchId?: string | null
}

export class Tap {
  private _id: string
  private _name: string
  private _tapNumber: number | null
  private _glassSize: number | null
  private _location: string
  private _notes: string
  private _token: string
  private _createdAt: string
  private _updatedAt: string
  private _lastCleanedAt: string
  private _vesselName: string | null
  private _volumeRemaining: number | null
  private _batchName: string | null
  private _batchId: string | null

  constructor({
    id = '',
    name = '',
    tapNumber = null,
    glassSize = null,
    location = '',
    notes = '',
    token = '',
    createdAt = '',
    updatedAt = '',
    lastCleanedAt = '',
    vesselName = null,
    volumeRemaining = null,
    batchName = null,
    batchId = null
  }: TapParams = {}) {
    this._id = id
    this._name = name
    this._tapNumber = tapNumber
    this._glassSize = glassSize
    this._location = location ?? ''
    this._notes = notes ?? ''
    this._token = token ?? ''
    this._createdAt = createdAt
    this._updatedAt = updatedAt
    this._lastCleanedAt = lastCleanedAt
    this._vesselName = vesselName
    this._volumeRemaining = volumeRemaining
    this._batchName = batchName
    this._batchId = batchId
  }

  static compare(t1: Tap, t2: Tap): boolean {
    return (
      t1.name === t2.name &&
      t1.tapNumber === t2.tapNumber &&
      t1.glassSize === t2.glassSize &&
      t1.location === t2.location &&
      t1.notes === t2.notes
    )
  }

  static fromJson(t: Record<string, unknown>): Tap {
    return new Tap({
      id: t.id as string,
      name: t.name as string,
      tapNumber: (t.tapNumber as number | null) ?? null,
      glassSize: (t.glassSize as number | null) ?? null,
      location: (t.location as string) ?? '',
      notes: (t.notes as string) ?? '',
      token: (t.token as string) ?? '',
      createdAt: (t.createdAt as string) ?? '',
      updatedAt: (t.updatedAt as string) ?? '',
      lastCleanedAt: (t.lastCleanedAt as string) ?? '',
      vesselName: (t.vesselName as string | null) ?? null,
      volumeRemaining: (t.volumeRemaining as number | null) ?? null,
      batchName: (t.batchName as string | null) ?? null,
      batchId: (t.batchId as string | null) ?? null
    })
  }

  toJson(): Record<string, unknown> {
    return {
      name: this.name,
      tapNumber: this.tapNumber,
      glassSize: this.glassSize,
      location: this.location,
      notes: this.notes
    }
  }

  get id() {
    return this._id
  }
  get name() {
    return this._name
  }
  get tapNumber() {
    return this._tapNumber
  }
  get glassSize() {
    return this._glassSize
  }
  get location() {
    return this._location
  }
  get notes() {
    return this._notes
  }
  get token() {
    return this._token
  }
  get createdAt() {
    return this._createdAt
  }
  get updatedAt() {
    return this._updatedAt
  }
  get lastCleanedAt() {
    return this._lastCleanedAt
  }
  get vesselName() {
    return this._vesselName
  }  get volumeRemaining() {
    return this._volumeRemaining
  }
  get batchName() {
    return this._batchName
  }  get batchId() {
    return this._batchId
  }

  set id(v: string) {
    this._id = v
  }
  set name(v: string) {
    this._name = v
  }
  set tapNumber(v: number | null) {
    this._tapNumber = v
  }
  set glassSize(v: number | null) {
    this._glassSize = v
  }
  set location(v: string) {
    this._location = v
  }
  set notes(v: string) {
    this._notes = v
  }
  set token(v: string) {
    this._token = v
  }
  set createdAt(v: string) {
    this._createdAt = v
  }
  set updatedAt(v: string) {
    this._updatedAt = v
  }
  set lastCleanedAt(v: string) {
    this._lastCleanedAt = v
  }
  set vesselName(v: string | null) {
    this._vesselName = v
  }  set volumeRemaining(v: number | null) {
    this._volumeRemaining = v
  }
  set batchName(v: string | null) {
    this._batchName = v
  }  set batchId(v: string | null) {
    this._batchId = v
  }
}
