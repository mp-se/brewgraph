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

export interface BrewfatherFermentationStep {
  order: number
  date: string
  temp: number
  days: number
  type: string
}

export interface BrewfatherDryHop {
  name: string
  amount: number
  trigger_hours_before: number
}

interface BrewfatherBatchParams {
  brewfatherId?: string
  name?: string
  brewDate?: string
  style?: string
  brewer?: string
  abv?: number
  ebc?: number
  ibu?: number
  og?: number
  fg?: number
  carbonation?: number
  volume?: number
  yeastName?: string
  yeastProductId?: string
  fermentationSteps?: BrewfatherFermentationStep[]
  dryHops?: BrewfatherDryHop[]
}

export class BrewfatherBatch {
  private _brewfatherId: string
  private _name: string
  private _brewDate: string
  private _style: string
  private _brewer: string
  private _abv: number
  private _ebc: number
  private _ibu: number
  private _og: number
  private _fg: number
  private _carbonation: number
  private _volume: number
  private _yeastName: string
  private _yeastProductId: string
  private _fermentationSteps: BrewfatherFermentationStep[]
  private _dryHops: BrewfatherDryHop[]

  constructor({
    brewfatherId = '',
    name = '',
    brewDate = '',
    style = '',
    brewer = '',
    abv = 0,
    ebc = 0,
    ibu = 0,
    og = 0,
    fg = 0,
    carbonation = 0,
    volume = 0,
    yeastName = '',
    yeastProductId = '',
    fermentationSteps = [],
    dryHops = []
  }: BrewfatherBatchParams = {}) {
    this._name = name
    this._brewDate = brewDate
    this._style = style
    this._brewer = brewer
    this._abv = abv
    this._ebc = ebc
    this._ibu = ibu
    this._og = og
    this._fg = fg
    this._carbonation = carbonation
    this._volume = volume
    this._yeastName = yeastName
    this._yeastProductId = yeastProductId
    this._brewfatherId = brewfatherId
    this._fermentationSteps = fermentationSteps
    this._dryHops = dryHops
  }

  static fromJson(d: Record<string, unknown>): BrewfatherBatch {
    return new BrewfatherBatch({
      brewfatherId: d.brewfatherId as string,
      name: d.name as string,
      brewDate: d.brewDate as string,
      style: d.style as string,
      brewer: d.brewer as string,
      abv: d.abv as number,
      ebc: d.ebc as number,
      ibu: d.ibu as number,
      og: d.og as number,
      fg: d.fg as number,
      carbonation: (d.carbonation as number) ?? 0,
      volume: (d.volume as number) ?? 0,
      yeastName: (d.yeast_name as string) ?? '',
      yeastProductId: (d.yeast_product_id as string) ?? '',
      fermentationSteps: (d.fermentationSteps as BrewfatherFermentationStep[]) ?? [],
      dryHops: (d.dryHops as BrewfatherDryHop[]) ?? []
    })
  }

  get brewfatherId() { return this._brewfatherId }
  get name() { return this._name }
  get brewDate() { return this._brewDate }
  get style() { return this._style }
  get brewer() { return this._brewer }
  get abv() { return this._abv }
  get ebc() { return this._ebc }
  get ibu() { return this._ibu }
  get og() { return this._og }
  get fg() { return this._fg }
  get yeastName() { return this._yeastName }
  get yeastProductId() { return this._yeastProductId }
  get volume() { return this._volume }
  get carbonation() { return this._carbonation }
  get fermentationSteps() { return this._fermentationSteps }
  get dryHops() { return this._dryHops }

  set brewfatherId(v: string) { this._brewfatherId = v }
  set name(v: string) { this._name = v }
  set brewDate(v: string) { this._brewDate = v }
  set style(v: string) { this._style = v }
  set brewer(v: string) { this._brewer = v }
  set abv(v: number) { this._abv = v }
  set ebc(v: number) { this._ebc = v }
  set ibu(v: number) { this._ibu = v }
  set og(v: number) { this._og = v }
  set fg(v: number) { this._fg = v }
  set yeastName(v: string) { this._yeastName = v }
  set yeastProductId(v: string) { this._yeastProductId = v }
  set volume(v: number) { this._volume = v }
  set carbonation(v: number) { this._carbonation = v }
  set fermentationSteps(v: BrewfatherFermentationStep[]) { this._fermentationSteps = v }
  set dryHops(v: BrewfatherDryHop[]) { this._dryHops = v }
}
