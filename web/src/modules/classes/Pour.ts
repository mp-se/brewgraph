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

interface PourParams {
  id?: number
  pour?: number
  volume?: number
  maxVolume?: number
  created?: string
  batchId?: number
  active?: boolean
}

export class Pour {
  private _id: number
  private _pour: number
  private _volume: number
  private _maxVolume: number
  private _created: string
  private _batchId: number
  private _active: boolean

  constructor({
    id = 0,
    pour = 0.0,
    volume = 0.0,
    maxVolume = 0.0,
    created = '',
    batchId = 0,
    active = true
  }: PourParams = {}) {
    this._id = id
    this._pour = pour
    this._volume = volume
    this._maxVolume = maxVolume
    this._created = created
    this._batchId = batchId
    this._active = active
  }

  static fromJson(p: Record<string, unknown>): Pour {
    return new Pour({
      id: p.id as number,
      pour: p.pour as number,
      volume: p.volume as number,
      maxVolume: p.maxVolume as number,
      created: p.created as string,
      batchId: p.batchId as number,
      active: p.active as boolean
    })
  }

  toJson(): Record<string, unknown> {
    return {
      pour: this.pour,
      volume: this.volume,
      maxVolume: this.maxVolume,
      created: this.created,
      active: this.active,
      batchId: this.batchId
    }
  }

  get id() {
    return this._id
  }
  get pour() {
    return this._pour
  }
  get volume() {
    return this._volume
  }
  get maxVolume() {
    return this._maxVolume
  }
  get created() {
    return this._created
  }
  get batchId() {
    return this._batchId
  }
  get active() {
    return this._active
  }

  set id(v: number) {
    this._id = v
  }
  set pour(v: number) {
    this._pour = v
  }
  set volume(v: number) {
    this._volume = v
  }
  set maxVolume(v: number) {
    this._maxVolume = v
  }
  set created(v: string) {
    this._created = v
  }
  set batchId(v: number) {
    this._batchId = v
  }
  set active(v: boolean) {
    this._active = v
  }
}
