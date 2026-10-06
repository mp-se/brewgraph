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

interface PourEventParams {
  id?: string
  vesselId?: string
  pourAmount?: number
  volumeRemaining?: number
  isManual?: boolean
  excluded?: boolean
  createdAt?: string
}

export class PourEvent {
  private _id: string
  private _vesselId: string
  private _pourAmount: number
  private _volumeRemaining: number
  private _isManual: boolean
  private _excluded: boolean
  private _createdAt: string

  constructor({
    id = '',
    vesselId = '',
    pourAmount = 0.0,
    volumeRemaining = 0.0,
    isManual = false,
    excluded = false,
    createdAt = ''
  }: PourEventParams = {}) {
    this._id = id
    this._vesselId = vesselId
    this._pourAmount = pourAmount ?? 0.0
    this._volumeRemaining = volumeRemaining ?? 0.0
    this._isManual = isManual ?? false
    this._excluded = excluded ?? false
    this._createdAt = createdAt ?? ''
  }

  static fromJson(p: Record<string, unknown>): PourEvent {
    return new PourEvent({
      id: p.id as string,
      vesselId: p.vesselId as string,
      pourAmount: p.pourAmount as number,
      volumeRemaining: p.volumeRemaining as number,
      isManual: (p.isManual as boolean) ?? false,
      excluded: (p.excluded as boolean) ?? false,
      createdAt: (p.createdAt as string) ?? ''
    })
  }

  toJson(): Record<string, unknown> {
    return {
      pourAmount: this.pourAmount
    }
  }

  get id() {
    return this._id
  }
  get vesselId() {
    return this._vesselId
  }
  get pourAmount() {
    return this._pourAmount
  }
  get volumeRemaining() {
    return this._volumeRemaining
  }
  get isManual() {
    return this._isManual
  }
  get excluded() {
    return this._excluded
  }
  get createdAt() {
    return this._createdAt
  }

  set id(v: string) {
    this._id = v
  }
  set vesselId(v: string) {
    this._vesselId = v
  }
  set pourAmount(v: number) {
    this._pourAmount = v
  }
  set volumeRemaining(v: number) {
    this._volumeRemaining = v
  }
  set isManual(v: boolean) {
    this._isManual = v
  }
  set excluded(v: boolean) {
    this._excluded = v
  }
  set createdAt(v: string) {
    this._createdAt = v
  }
}
