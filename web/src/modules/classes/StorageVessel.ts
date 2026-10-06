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

interface StorageVesselParams {
  id?: string
  batchId?: string
  tapId?: string | null
  vesselNumber?: number | null
  vesselType?: string
  name?: string
  fillDate?: string
  conditioningDays?: number | null
  totalVolume?: number
  volumeRemaining?: number
  bottleVolume?: number | null
  bottleCount?: number | null
  bottlesRemaining?: number | null
  status?: string
  location?: string
  notes?: string
  createdAt?: string
  updatedAt?: string
  pourCount?: number
  batchName?: string | null
  kegIdentifier?: string | null
  fillCount?: number
  carbonationVolumesTarget?: number | null
}

export class StorageVessel {
  private _id: string
  private _batchId: string
  private _tapId: string | null
  private _vesselNumber: number | null
  private _vesselType: string
  private _name: string
  private _fillDate: string
  private _conditioningDays: number | null
  private _totalVolume: number
  private _volumeRemaining: number
  private _bottleVolume: number | null
  private _bottleCount: number | null
  private _bottlesRemaining: number | null
  private _status: string
  private _location: string
  private _notes: string
  private _createdAt: string
  private _updatedAt: string
  private _pourCount: number
  private _batchName: string | null
  private _kegIdentifier: string | null
  private _fillCount: number
  private _carbonationVolumesTarget: number | null

  constructor({
    id = '',
    batchId = '',
    tapId = null,
    vesselNumber = null,
    vesselType = 'keg',
    name = '',
    fillDate = '',
    conditioningDays = null,
    totalVolume = 0.0,
    volumeRemaining = 0.0,
    bottleVolume = null,
    bottleCount = null,
    bottlesRemaining = null,
    status = 'filled',
    location = '',
    notes = '',
    createdAt = '',
    updatedAt = '',
    pourCount = 0,
    batchName = null,
    kegIdentifier = null,
    fillCount = 1,
    carbonationVolumesTarget = null
  }: StorageVesselParams = {}) {
    this._id = id
    this._batchId = batchId
    this._tapId = tapId
    this._vesselNumber = vesselNumber
    this._vesselType = vesselType
    this._name = name
    this._fillDate = fillDate
    this._conditioningDays = conditioningDays ?? null
    this._totalVolume = totalVolume
    this._volumeRemaining = volumeRemaining
    this._bottleVolume = bottleVolume
    this._bottleCount = bottleCount
    this._bottlesRemaining = bottlesRemaining
    this._status = status
    this._location = location ?? ''
    this._notes = notes ?? ''
    this._createdAt = createdAt
    this._updatedAt = updatedAt
    this._pourCount = pourCount
    this._batchName = batchName ?? null
    this._kegIdentifier = kegIdentifier ?? null
    this._fillCount = fillCount ?? 1
    this._carbonationVolumesTarget = carbonationVolumesTarget ?? null
  }

  static fromJson(v: Record<string, unknown>): StorageVessel {
    return new StorageVessel({
      id: v.id as string,
      batchId: v.batchId as string,
      tapId: (v.tapId as string | null) ?? null,
      vesselNumber: (v.vesselNumber as number | null) ?? null,
      vesselType: v.vesselType as string,
      name: v.name as string,
      fillDate: (v.fillDate as string) ?? '',
      conditioningDays: (v.conditioningDays as number | null) ?? null,
      totalVolume: v.totalVolume as number,
      volumeRemaining: v.volumeRemaining as number,
      bottleVolume: (v.bottleVolume as number | null) ?? null,
      bottleCount: (v.bottleCount as number | null) ?? null,
      bottlesRemaining: (v.bottlesRemaining as number | null) ?? null,
      status: v.status as string,
      location: (v.location as string) ?? '',
      notes: (v.notes as string) ?? '',
      createdAt: (v.createdAt as string) ?? '',
      updatedAt: (v.updatedAt as string) ?? '',
      pourCount: (v.pourCount as number) ?? 0,
      batchName: (v.batchName as string | null) ?? null,
      kegIdentifier: (v.kegIdentifier as string | null) ?? null,
      fillCount: (v.fillCount as number) ?? 1,
      carbonationVolumesTarget: (v.carbonationVolumesTarget as number | null) ?? null
    })
  }

  static compare(v1: StorageVessel, v2: StorageVessel): boolean {
    return (
      v1.name === v2.name &&
      (v1.batchId || null) === (v2.batchId || null) &&
      v1.tapId === v2.tapId &&
      v1.vesselNumber === v2.vesselNumber &&
      v1.vesselType === v2.vesselType &&
      v1.fillDate === v2.fillDate &&
      v1.conditioningDays === v2.conditioningDays &&
      v1.totalVolume === v2.totalVolume &&
      v1.volumeRemaining === v2.volumeRemaining &&
      v1.bottleVolume === v2.bottleVolume &&
      v1.bottleCount === v2.bottleCount &&
      v1.bottlesRemaining === v2.bottlesRemaining &&
      v1.status === v2.status &&
      v1.location === v2.location &&
      v1.notes === v2.notes
    )
  }

  toJson(): Record<string, unknown> {
    return {
      batchId: this.batchId || null,
      tapId: this.tapId,
      vesselNumber: this.vesselNumber,
      vesselType: this.vesselType,
      name: this.name,
      fillDate: this.fillDate || null,
      conditioningDays: this.conditioningDays,
      totalVolume: this.totalVolume,
      volumeRemaining: this.volumeRemaining,
      bottleVolume: this.bottleVolume,
      bottleCount: this.bottleCount,
      bottlesRemaining: this.bottlesRemaining,
      status: this.status,
      location: this.location,
      notes: this.notes
    }
  }

  get id() {
    return this._id
  }
  get batchId() {
    return this._batchId
  }
  get tapId() {
    return this._tapId
  }
  get vesselNumber() {
    return this._vesselNumber
  }
  get vesselType() {
    return this._vesselType
  }
  get name() {
    return this._name
  }
  get fillDate() {
    return this._fillDate
  }
  get conditioningDays() {
    return this._conditioningDays
  }
  get totalVolume() {
    return this._totalVolume
  }
  get volumeRemaining() {
    return this._volumeRemaining
  }
  get bottleVolume() {
    return this._bottleVolume
  }
  get bottleCount() {
    return this._bottleCount
  }
  get bottlesRemaining() {
    return this._bottlesRemaining
  }
  get status() {
    return this._status
  }
  get isOnTap() {
    return this._tapId !== null
  }
  get isEmpty() {
    if (this._vesselType === 'bottles') return (this._bottlesRemaining ?? 0) <= 0
    return this._volumeRemaining <= 0
  }
  get location() {
    return this._location
  }
  get notes() {
    return this._notes
  }
  get createdAt() {
    return this._createdAt
  }
  get updatedAt() {
    return this._updatedAt
  }
  get pourCount() {
    return this._pourCount
  }
  get batchName() {
    return this._batchName
  }
  get kegIdentifier() {
    return this._kegIdentifier
  }
  get fillCount() {
    return this._fillCount
  }
  get carbonationVolumesTarget() {
    return this._carbonationVolumesTarget
  }

  set id(v: string) {
    this._id = v
  }
  set batchId(v: string) {
    this._batchId = v
  }
  set tapId(v: string | null) {
    this._tapId = v
  }
  set vesselNumber(v: number | null) {
    this._vesselNumber = v
  }
  set vesselType(v: string) {
    this._vesselType = v
  }
  set name(v: string) {
    this._name = v
  }
  set fillDate(v: string) {
    this._fillDate = v
  }
  set conditioningDays(v: number | null) {
    this._conditioningDays = v
  }
  set totalVolume(v: number) {
    this._totalVolume = v
  }
  set volumeRemaining(v: number) {
    this._volumeRemaining = v
  }
  set bottleVolume(v: number | null) {
    this._bottleVolume = v
  }
  set bottleCount(v: number | null) {
    this._bottleCount = v
  }
  set bottlesRemaining(v: number | null) {
    this._bottlesRemaining = v
  }
  set status(v: string) {
    this._status = v
  }
  set location(v: string) {
    this._location = v
  }
  set notes(v: string) {
    this._notes = v
  }
  set createdAt(v: string) {
    this._createdAt = v
  }
  set updatedAt(v: string) {
    this._updatedAt = v
  }
  set pourCount(v: number) {
    this._pourCount = v
  }
  set batchName(v: string | null) {
    this._batchName = v
  }
}
