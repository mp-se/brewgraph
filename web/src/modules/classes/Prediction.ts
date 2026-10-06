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

interface PredictionParams {
  id?: number
  batchId?: string
  deviceId?: string
  vesselId?: string
  predictionType?: string
  outcome?: string
  hoursLeft?: number | null
  createdAt?: string
}

export class Prediction {
  private _id: number
  private _batchId: string
  private _deviceId: string
  private _vesselId: string
  private _predictionType: string
  private _outcome: string
  private _hoursLeft: number | null
  private _createdAt: string

  constructor({
    id = 0,
    batchId = '',
    deviceId = '',
    vesselId = '',
    predictionType = '',
    outcome = '',
    hoursLeft = null,
    createdAt = ''
  }: PredictionParams = {}) {
    this._id = id
    this._batchId = batchId
    this._deviceId = deviceId
    this._vesselId = vesselId
    this._predictionType = predictionType
    this._outcome = outcome
    this._hoursLeft = hoursLeft ?? null
    this._createdAt = createdAt
  }

  static fromJson(p: Record<string, unknown>): Prediction {
    return new Prediction({
      id: (p.id as number) ?? 0,
      batchId: (p.batchId as string) ?? '',
      deviceId: (p.deviceId as string) ?? '',
      vesselId: (p.vesselId as string) ?? '',
      predictionType: (p.predictionType as string) ?? '',
      outcome: (p.outcome as string) ?? '',
      hoursLeft: (p.hoursLeft as number | null) ?? null,
      createdAt: (p.createdAt as string) ?? ''
    })
  }

  toJson(): Record<string, unknown> {
    return {
      batchId: this._batchId,
      deviceId: this._deviceId,
      vesselId: this._vesselId,
      predictionType: this._predictionType,
      outcome: this._outcome,
      hoursLeft: this._hoursLeft
    }
  }

  static compare(a: Prediction, b: Prediction): boolean {
    return (
      a.id === b.id &&
      a.batchId === b.batchId &&
      a.deviceId === b.deviceId &&
      a.vesselId === b.vesselId &&
      a.predictionType === b.predictionType &&
      a.outcome === b.outcome &&
      a.hoursLeft === b.hoursLeft &&
      a.createdAt === b.createdAt
    )
  }

  get id() {
    return this._id
  }
  get batchId() {
    return this._batchId
  }
  get deviceId() {
    return this._deviceId
  }
  get vesselId() {
    return this._vesselId
  }
  get predictionType() {
    return this._predictionType
  }
  get outcome() {
    return this._outcome
  }
  get hoursLeft() {
    return this._hoursLeft
  }
  get createdAt() {
    return this._createdAt
  }

  set id(v: number) {
    this._id = v
  }
  set batchId(v: string) {
    this._batchId = v
  }
  set deviceId(v: string) {
    this._deviceId = v
  }
  set vesselId(v: string) {
    this._vesselId = v
  }
  set predictionType(v: string) {
    this._predictionType = v
  }
  set outcome(v: string) {
    this._outcome = v
  }
  set hoursLeft(v: number | null) {
    this._hoursLeft = v
  }
  set createdAt(v: string) {
    this._createdAt = v
  }
}
