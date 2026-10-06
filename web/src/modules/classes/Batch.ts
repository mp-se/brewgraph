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

interface BatchParams {
  id?: string
  name?: string
  description?: string
  acceptIngest?: boolean
  gravityDeviceId?: string | null
  pressureDeviceId?: string | null
  chamberDeviceId?: string | null
  tempDeviceId?: string | null
  brewDate?: string
  style?: string
  brewer?: string
  abv?: number
  ebc?: number | null
  ibu?: number | null
  fg?: number | null
  og?: number | null
  carbonationVolumes?: number | null
  volume?: number | null
  packageDate?: string
  conditioningDays?: number | null
  brewfatherBatchId?: string
  notes?: string
  gravityCount?: number | null
  pressureCount?: number | null
  temperatureCount?: number | null
  maxGravityReading?: Record<string, unknown> | null
  minGravityReading?: Record<string, unknown> | null
  maxPressureReading?: Record<string, unknown> | null
  minPressureReading?: Record<string, unknown> | null
  fermentationChamber?: string | null
  chamberControlActive?: boolean
  fermentationSteps?: string
  yeast?: string
  yeastProductId?: string
  createdAt?: string
  updatedAt?: string
  status?: string
}

export class Batch {
  private _id: string
  private _name: string
  private _description: string
  private _acceptIngest: boolean
  private _gravityDeviceId: string | null
  private _pressureDeviceId: string | null
  private _chamberDeviceId: string | null
  private _tempDeviceId: string | null
  private _brewDate: string
  private _style: string
  private _brewer: string
  private _abv: number
  private _ebc: number | null
  private _ibu: number | null
  private _fg: number | null
  private _og: number | null
  private _carbonationVolumes: number | null
  private _volume: number | null
  private _packageDate: string
  private _conditioningDays: number | null
  private _brewfatherBatchId: string
  private _notes: string
  private _gravityCount: number
  private _pressureCount: number
  private _temperatureCount: number
  private _maxGravityReading: Record<string, unknown> | null
  private _minGravityReading: Record<string, unknown> | null
  private _maxPressureReading: Record<string, unknown> | null
  private _minPressureReading: Record<string, unknown> | null
  private _fermentationChamber: string | null
  private _chamberControlActive: boolean
  private _fermentationSteps: string
  private _yeast: string
  private _yeastProductId: string
  private _createdAt: string
  private _updatedAt: string
  private _status: string

  constructor({
    id = '',
    name = '',
    description = '',
    acceptIngest = true,
    gravityDeviceId = null,
    pressureDeviceId = null,
    chamberDeviceId = null,
    tempDeviceId = null,
    brewDate = '',
    style = '',
    brewer = '',
    abv = 0,
    ebc = null,
    ibu = null,
    fg = null,
    og = null,
    carbonationVolumes = null,
    volume = null,
    packageDate = '',
    conditioningDays = null,
    brewfatherBatchId = '',
    notes = '',
    gravityCount = 0,
    pressureCount = 0,
    temperatureCount = 0,
    maxGravityReading = null,
    minGravityReading = null,
    maxPressureReading = null,
    minPressureReading = null,
    fermentationChamber = null,
    chamberControlActive = false,
    fermentationSteps = '',
    yeast = '',
    yeastProductId = '',
    createdAt = '',
    updatedAt = '',
    status = 'fermenting'
  }: BatchParams = {}) {
    this._id = id
    this._name = name
    this._description = description
    this._acceptIngest = acceptIngest
    this._gravityDeviceId = gravityDeviceId
    this._pressureDeviceId = pressureDeviceId
    this._chamberDeviceId = chamberDeviceId
    this._tempDeviceId = tempDeviceId
    this._brewDate = brewDate
    this._style = style
    this._brewer = brewer
    this._abv = abv
    this._ebc = ebc
    this._ibu = ibu
    this._fg = fg
    this._og = og
    this._carbonationVolumes = carbonationVolumes
    this._volume = volume
    this._packageDate = packageDate
    this._conditioningDays = conditioningDays
    this._brewfatherBatchId = brewfatherBatchId
    this._notes = notes === null ? '' : notes
    this._gravityCount = gravityCount === null ? 0 : gravityCount
    this._pressureCount = pressureCount === null ? 0 : pressureCount
    this._temperatureCount = temperatureCount === null ? 0 : temperatureCount
    this._maxGravityReading = maxGravityReading ?? null
    this._minGravityReading = minGravityReading ?? null
    this._maxPressureReading = maxPressureReading ?? null
    this._minPressureReading = minPressureReading ?? null
    this._fermentationChamber = fermentationChamber ?? null
    this._chamberControlActive = chamberControlActive ?? false
    this._fermentationSteps = fermentationSteps ?? ''
    this._yeast = yeast ?? ''
    this._yeastProductId = yeastProductId ?? ''
    this._createdAt = createdAt
    this._updatedAt = updatedAt
    this._status = status
  }

  static compare(b1: Batch, b2: Batch): boolean {
    return (
      b1.name === b2.name &&
      b1.description === b2.description &&
      b1.acceptIngest === b2.acceptIngest &&
      b1.gravityDeviceId === b2.gravityDeviceId &&
      b1.pressureDeviceId === b2.pressureDeviceId &&
      b1.chamberDeviceId === b2.chamberDeviceId &&
      b1.brewDate === b2.brewDate &&
      b1.style === b2.style &&
      b1.brewer === b2.brewer &&
      b1.abv === b2.abv &&
      b1.ebc === b2.ebc &&
      b1.ibu === b2.ibu &&
      b1.fg === b2.fg &&
      b1.og === b2.og &&
      b1.carbonationVolumes === b2.carbonationVolumes &&
      b1.volume === b2.volume &&
      b1.packageDate === b2.packageDate &&
      b1.conditioningDays === b2.conditioningDays &&
      b1.brewfatherBatchId === b2.brewfatherBatchId &&
      b1.notes === b2.notes &&
      b1.yeast === b2.yeast &&
      b1.yeastProductId === b2.yeastProductId &&
      b1.fermentationSteps === b2.fermentationSteps
    )
  }

  static fromJson(b: Record<string, unknown>): Batch {
    return new Batch({
      id: b.id as string,
      name: b.name as string,
      description: b.description as string,
      acceptIngest: (b.acceptIngest as boolean) ?? true,
      brewDate: (b.brewDate as string) ?? '',
      style: (b.style as string) ?? '',
      brewer: (b.brewer as string) ?? '',
      abv: (b.abv as number) ?? 0,
      ebc: (b.ebc as number | null) ?? null,
      ibu: (b.ibu as number | null) ?? null,
      fg: (b.fg as number | null) ?? null,
      og: (b.og as number | null) ?? null,
      carbonationVolumes: (b.carbonationVolumes as number | null) ?? null,
      volume: (b.volume as number | null) ?? null,
      packageDate: (b.packageDate as string) ?? '',
      conditioningDays: (b.conditioningDays as number | null) ?? null,
      brewfatherBatchId: (b.brewfatherBatchId as string) ?? '',
      notes: (b.notes as string) ?? '',
      gravityCount: (b.gravityCount as number) ?? 0,
      pressureCount: (b.pressureCount as number) ?? 0,
      temperatureCount: (b.temperatureCount as number) ?? 0,
      fermentationChamber: (b.fermentationChamber as string | null) ?? null,
      chamberControlActive: (b.chamberControlActive as boolean) ?? false,
      fermentationSteps: (b.fermentationSteps as string) ?? '',
      yeast: (b.yeast as string) ?? '',
      yeastProductId: (b.yeastProductId as string) ?? '',
      createdAt: (b.createdAt as string) ?? '',
      updatedAt: (b.updatedAt as string) ?? '',
      status: (b.status as string) ?? 'fermenting'
    })
  }

  static fromDashboardJson(bd: Record<string, unknown>): Batch {
    return new Batch({
      id: bd.id as string,
      name: bd.name as string,
      acceptIngest: (bd.acceptIngest as boolean) ?? true,
      gravityCount: (bd.gravityCount as number) ?? 0,
      pressureCount: (bd.pressureCount as number) ?? 0,
      temperatureCount: (bd.temperatureCount as number) ?? 0,
      maxGravityReading: (bd.maxGravityReading as Record<string, unknown>) ?? null,
      minGravityReading: (bd.minGravityReading as Record<string, unknown>) ?? null,
      maxPressureReading: (bd.maxPressureReading as Record<string, unknown>) ?? null,
      minPressureReading: (bd.minPressureReading as Record<string, unknown>) ?? null
    })
  }

  toJson(): Record<string, unknown> {
    return {
      name: this.name,
      description: this.description,
      acceptIngest: this.acceptIngest,
      brewDate: this.brewDate || null,
      style: this.style,
      brewer: this.brewer,
      abv: this.abv,
      ebc: this.ebc,
      ibu: this.ibu,
      fg: this.fg,
      og: this.og,
      carbonationVolumes: this.carbonationVolumes,
      volume: this.volume,
      packageDate: this.packageDate || null,
      conditioningDays: this.conditioningDays,
      brewfatherBatchId: this.brewfatherBatchId,
      notes: this.notes,
      yeast: this.yeast,
      yeastProductId: this.yeastProductId
    }
  }

  get id() {
    return this._id
  }
  get name() {
    return this._name
  }
  get description() {
    return this._description
  }
  get acceptIngest() {
    return this._acceptIngest
  }
  get gravityDeviceId() {
    return this._gravityDeviceId
  }
  get pressureDeviceId() {
    return this._pressureDeviceId
  }
  get chamberDeviceId() {
    return this._chamberDeviceId
  }
  get tempDeviceId() {
    return this._tempDeviceId
  }
  get brewDate() {
    return this._brewDate
  }
  get style() {
    return this._style
  }
  get brewer() {
    return this._brewer
  }
  get abv() {
    return this._abv
  }
  get ebc() {
    return this._ebc
  }
  get ibu() {
    return this._ibu
  }
  get fg() {
    return this._fg
  }
  get og() {
    return this._og
  }
  get carbonationVolumes() {
    return this._carbonationVolumes
  }
  get volume() {
    return this._volume
  }
  get packageDate() {
    return this._packageDate
  }
  get conditioningDays() {
    return this._conditioningDays
  }
  get readyDate(): string | null {
    if (!this._packageDate || !this._conditioningDays) return null
    const d = new Date(this._packageDate)
    d.setDate(d.getDate() + this._conditioningDays)
    return d.toISOString().slice(0, 10)
  }
  get brewfatherBatchId() {
    return this._brewfatherBatchId
  }
  get notes() {
    return this._notes
  }
  get gravityCount() {
    return this._gravityCount
  }
  get pressureCount() {
    return this._pressureCount
  }
  get temperatureCount() {
    return this._temperatureCount
  }
  get maxGravityReading() {
    return this._maxGravityReading
  }
  get minGravityReading() {
    return this._minGravityReading
  }
  get maxPressureReading() {
    return this._maxPressureReading
  }
  get minPressureReading() {
    return this._minPressureReading
  }
  get fermentationChamber() {
    return this._fermentationChamber
  }
  /** True while the chamber is following this batch's step schedule. */
  get chamberControlActive() {
    return this._chamberControlActive
  }
  get fermentationSteps() {
    return this._fermentationSteps
  }
  get yeast() {
    return this._yeast
  }
  get yeastProductId() {
    return this._yeastProductId
  }
  get createdAt() {
    return this._createdAt
  }
  get updatedAt() {
    return this._updatedAt
  }
  get status() {
    return this._status
  }

  set id(v: string) {
    this._id = v
  }
  set name(v: string) {
    this._name = v
  }
  set description(v: string) {
    this._description = v
  }
  set acceptIngest(v: boolean) {
    this._acceptIngest = v
  }
  set gravityDeviceId(v: string | null) {
    this._gravityDeviceId = v
  }
  set pressureDeviceId(v: string | null) {
    this._pressureDeviceId = v
  }
  set chamberDeviceId(v: string | null) {
    this._chamberDeviceId = v
  }
  set tempDeviceId(v: string | null) {
    this._tempDeviceId = v
  }
  set brewDate(v: string) {
    this._brewDate = v
  }
  set style(v: string) {
    this._style = v
  }
  set brewer(v: string) {
    this._brewer = v
  }
  set abv(v: number) {
    this._abv = v
  }
  set ebc(v: number | null) {
    this._ebc = v
  }
  set ibu(v: number | null) {
    this._ibu = v
  }
  set fg(v: number | null) {
    this._fg = v
  }
  set og(v: number | null) {
    this._og = v
  }
  set carbonationVolumes(v: number | null) {
    this._carbonationVolumes = v
  }
  set volume(v: number | null) {
    this._volume = v
  }
  set packageDate(v: string) {
    this._packageDate = v
  }
  set conditioningDays(v: number | null) {
    this._conditioningDays = v
  }
  set brewfatherBatchId(v: string) {
    this._brewfatherBatchId = v
  }
  set notes(v: string) {
    this._notes = v
  }
  set gravityCount(v: number) {
    this._gravityCount = v
  }
  set pressureCount(v: number) {
    this._pressureCount = v
  }
  set maxGravityReading(v: Record<string, unknown> | null) {
    this._maxGravityReading = v
  }
  set minGravityReading(v: Record<string, unknown> | null) {
    this._minGravityReading = v
  }
  set maxPressureReading(v: Record<string, unknown> | null) {
    this._maxPressureReading = v
  }
  set minPressureReading(v: Record<string, unknown> | null) {
    this._minPressureReading = v
  }
  set fermentationChamber(v: string | null) {
    this._fermentationChamber = v
  }
  set fermentationSteps(v: string) {
    this._fermentationSteps = v
  }
  set yeast(v: string) {
    this._yeast = v
  }
  set yeastProductId(v: string) {
    this._yeastProductId = v
  }
  set createdAt(v: string) {
    this._createdAt = v
  }
  set updatedAt(v: string) {
    this._updatedAt = v
  }
  set status(v: string) {
    this._status = v
  }
}
