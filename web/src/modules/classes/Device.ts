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

// Device type — canonical Device.device_type enum values (renamed from `software`,
// which used mixed-case display strings like 'Chamber-Controller')
export const DEVICE_TYPE_UNKNOWN = ''
export const DEVICE_TYPE_GRAVITYMON = 'gravitymon'
export const DEVICE_TYPE_GRAVITYMON_GW = 'gravitymon_gateway'
export const DEVICE_TYPE_KEGMON = 'kegmon'
export const DEVICE_TYPE_CHAMBER_CONTROLLER = 'chamber_controller'
export const DEVICE_TYPE_PRESSUREMON = 'pressuremon'
export const DEVICE_TYPE_ISPINDEL = 'ispindel'

export const deviceTypeOptions = [
  { label: '- unknown -', value: DEVICE_TYPE_UNKNOWN },
  { label: 'Gravitymon', value: DEVICE_TYPE_GRAVITYMON },
  { label: 'Gravitymon Gateway', value: DEVICE_TYPE_GRAVITYMON_GW },
  { label: 'Kegmon', value: DEVICE_TYPE_KEGMON },
  { label: 'Chamber Controller', value: DEVICE_TYPE_CHAMBER_CONTROLLER },
  { label: 'Pressuremon', value: DEVICE_TYPE_PRESSUREMON },
  { label: 'iSpindel', value: DEVICE_TYPE_ISPINDEL }
]

// Chip family values — match the backend ChipFamily enum (lowercase)
export const CHIP_FAMILY_UNKNOWN = ''
export const CHIP_FAMILY_ESP8266 = 'esp8266'
export const CHIP_FAMILY_ESP32 = 'esp32'
export const CHIP_FAMILY_ESP32C3 = 'esp32c3'
export const CHIP_FAMILY_ESP32S2 = 'esp32s2'
export const CHIP_FAMILY_ESP32S3 = 'esp32s3'

export const chipFamilyOptions = [
  { label: '- unknown -', value: CHIP_FAMILY_UNKNOWN },
  { label: 'ESP8266', value: CHIP_FAMILY_ESP8266 },
  { label: 'ESP32', value: CHIP_FAMILY_ESP32 },
  { label: 'ESP32-C3', value: CHIP_FAMILY_ESP32C3 },
  { label: 'ESP32-S2', value: CHIP_FAMILY_ESP32S2 },
  { label: 'ESP32-S3', value: CHIP_FAMILY_ESP32S3 }
]

export const DEVICE_COLOR_BLACK = 'black'
export const DEVICE_COLOR_RED = 'red'
export const DEVICE_COLOR_ORANGE = 'orange'
export const DEVICE_COLOR_YELLOW = 'yellow'
export const DEVICE_COLOR_GREEN = 'green'
export const DEVICE_COLOR_BLUE = 'blue'
export const DEVICE_COLOR_PURPLE = 'purple'
export const DEVICE_COLOR_PINK = 'pink'
export const DEVICE_COLOR_WHITE = 'white'

export const deviceColorOptions = [
  { label: 'Black', value: DEVICE_COLOR_BLACK },
  { label: 'Red', value: DEVICE_COLOR_RED },
  { label: 'Orange', value: DEVICE_COLOR_ORANGE },
  { label: 'Yellow', value: DEVICE_COLOR_YELLOW },
  { label: 'Green', value: DEVICE_COLOR_GREEN },
  { label: 'Blue', value: DEVICE_COLOR_BLUE },
  { label: 'Purple', value: DEVICE_COLOR_PURPLE },
  { label: 'Pink', value: DEVICE_COLOR_PINK },
  { label: 'White', value: DEVICE_COLOR_WHITE }
]

export interface FermentationStepData {
  id: string
  order: number
  type: string
  name: string
  temp: number
  days: number
  date: string
  control: string
  batchId: string
  deviceId: string | null
}

export interface GravityCalibrationPoint {
  angle: number
  gravity: number
}

interface DeviceParams {
  id?: string
  name?: string
  chipId?: string
  chipFamily?: string
  deviceType?: string
  mdns?: string
  config?: string
  deviceColor?: string
  url?: string
  description?: string
  collectLogs?: boolean
  token?: string
  fermentationStep?: FermentationStepData[]
  batchId?: string | null
  batchRole?: string | null
  vesselId?: string | null
  failedIngestCounter?: number
  gravityFormula?: string | null
  gravityFormulaUnit?: 'sg' | 'plato' | null
  gravityCalibrationData?: GravityCalibrationPoint[]
}

export class Device {
  private _id: string
  private _name: string
  private _chipId: string
  private _chipFamily: string
  private _deviceType: string
  private _mdns: string
  private _config: string
  private _deviceColor: string
  private _url: string
  private _description: string
  private _collectLogs: boolean
  private _token: string
  private _fermentationStep: FermentationStepData[]
  private _batchId: string | null
  private _batchRole: string | null
  private _vesselId: string | null
  private _failedIngestCounter: number
  private _gravityFormula: string | null
  private _gravityFormulaUnit: 'sg' | 'plato' | null
  private _gravityCalibrationData: GravityCalibrationPoint[]

  constructor({
    id = '',
    name = '',
    chipId = '',
    chipFamily = '',
    deviceType = '',
    mdns = '',
    config = '',
    deviceColor = DEVICE_COLOR_WHITE,
    url = '',
    description = '',
    collectLogs = false,
    token = '',
    fermentationStep = [],
    batchId = null,
    batchRole = null,
    vesselId = null,
    failedIngestCounter = 0,
    gravityFormula = null,
    gravityFormulaUnit = null,
    gravityCalibrationData = []
  }: DeviceParams = {}) {
    this._id = id
    this._name = name
    this._chipId = chipId
    this._chipFamily = chipFamily
    this._deviceType = deviceType
    this._mdns = mdns
    this._config = config
    this._deviceColor = deviceColor
    this._url = url === 'http://' || url === 'https://' ? '' : (url ?? '')
    this._description = description
    this._collectLogs = collectLogs
    this._token = token
    this._fermentationStep = fermentationStep ?? []
    this._batchId = batchId ?? null
    this._batchRole = batchRole ?? null
    this._vesselId = vesselId ?? null
    this._failedIngestCounter = failedIngestCounter ?? 0
    this._gravityFormula = gravityFormula ?? null
    this._gravityFormulaUnit = gravityFormulaUnit ?? null
    this._gravityCalibrationData = gravityCalibrationData ?? []
  }

  static compare(d1: Device, d2: Device): boolean {
    return (
      d1.name === d2.name &&
      d1.chipId === d2.chipId &&
      d1.chipFamily === d2.chipFamily &&
      d1.deviceType === d2.deviceType &&
      d1.mdns === d2.mdns &&
      // Config is JSON from the API and may be decoded as a fresh object on
      // every response; compare its value rather than object identity.
      JSON.stringify(d1.config) === JSON.stringify(d2.config) &&
      d1.deviceColor === d2.deviceColor &&
      d1.url === d2.url &&
      d1.description === d2.description &&
      d1.collectLogs === d2.collectLogs &&
      d1.batchId === d2.batchId &&
      d1.batchRole === d2.batchRole &&
      d1.vesselId === d2.vesselId &&
      d1.gravityFormula === d2.gravityFormula &&
      d1.gravityFormulaUnit === d2.gravityFormulaUnit &&
      JSON.stringify(d1.gravityCalibrationData) === JSON.stringify(d2.gravityCalibrationData)
    )
  }

  static fromJson(d: Record<string, unknown>): Device {
    return new Device({
      id: d.id as string,
      name: (d.name as string) ?? '',
      chipId: (d.chipId as string) ?? '',
      chipFamily: (d.chipFamily as string) ?? '',
      deviceType: (d.deviceType as string) ?? '',
      mdns: (d.mdns as string) ?? '',
      config: (d.config as string) ?? '',
      deviceColor: (d.deviceColor as string) ?? DEVICE_COLOR_WHITE,
      url: (d.url as string) ?? '',
      description: (d.description as string) ?? '',
      collectLogs: (d.collectLogs as boolean) ?? false,
      token: (d.token as string) ?? '',
      fermentationStep: (d.fermentationStep as FermentationStepData[]) ?? [],
      batchId: (d.batchId as string | null) ?? null,
      batchRole: (d.batchRole as string | null) ?? null,
      vesselId: (d.vesselId as string | null) ?? null,
      failedIngestCounter: (d.failedIngestCounter as number) ?? 0,
      gravityFormula: (d.gravityFormula as string | null) ?? null,
      gravityFormulaUnit: (d.gravityFormulaUnit as 'sg' | 'plato' | null) ?? null,
      gravityCalibrationData: (d.gravityCalibrationData as GravityCalibrationPoint[]) ?? []
    })
  }

  toJson(): Record<string, unknown> {
    return {
      name: this.name,
      chipId: this.chipId,
      chipFamily: this.chipFamily,
      deviceType: this.deviceType,
      mdns: this.mdns,
      config: this.config,
      deviceColor: this.deviceColor,
      url: this.url,
      description: this.description,
      collectLogs: this.collectLogs,
      batchId: this.batchId,
      batchRole: this.batchRole,
      vesselId: this.vesselId,
      gravityFormula: this.gravityFormula,
      gravityFormulaUnit: this.gravityFormulaUnit,
      gravityCalibrationData: this.gravityCalibrationData
    }
  }

  get id() {
    return this._id
  }
  get name() {
    return this._name
  }
  get chipId() {
    return this._chipId
  }
  get chipFamily() {
    return this._chipFamily
  }
  get deviceType() {
    return this._deviceType
  }
  get mdns() {
    return this._mdns
  }
  get config() {
    return this._config
  }
  get deviceColor() {
    return this._deviceColor
  }
  get url() {
    return this._url
  }
  get description() {
    return this._description
  }
  get collectLogs() {
    return this._collectLogs
  }
  get token() {
    return this._token
  }
  get fermentationStep() {
    return this._fermentationStep
  }
  get batchId() {
    return this._batchId
  }
  get batchRole() {
    return this._batchRole
  }
  get vesselId() {
    return this._vesselId
  }
  get failedIngestCounter() {
    return this._failedIngestCounter
  }
  get gravityFormula() { return this._gravityFormula }
  get gravityFormulaUnit() { return this._gravityFormulaUnit }
  get gravityCalibrationData() { return this._gravityCalibrationData }

  set id(v: string) {
    this._id = v
  }
  set name(v: string) {
    this._name = v
  }
  set chipId(v: string) {
    this._chipId = v
  }
  set chipFamily(v: string) {
    this._chipFamily = v
  }
  set deviceType(v: string) {
    this._deviceType = v
  }
  set mdns(v: string) {
    this._mdns = v
  }
  set config(v: string) {
    this._config = v
  }
  set deviceColor(v: string) {
    this._deviceColor = v
  }
  set url(v: string) {
    this._url = v
  }
  set description(v: string) {
    this._description = v
  }
  set collectLogs(v: boolean) {
    this._collectLogs = v
  }
  set token(v: string) {
    this._token = v
  }
  set batchId(v: string | null) {
    this._batchId = v
  }
  set batchRole(v: string | null) {
    this._batchRole = v
  }
  set vesselId(v: string | null) {
    this._vesselId = v
  }
  set gravityFormula(v: string | null) { this._gravityFormula = v }
  set gravityFormulaUnit(v: 'sg' | 'plato' | null) { this._gravityFormulaUnit = v }
  set gravityCalibrationData(v: GravityCalibrationPoint[]) { this._gravityCalibrationData = v }

  // Device type helpers — use these in the UI instead of comparing device_type strings directly

  get isGravitymon() {
    return this._deviceType === DEVICE_TYPE_GRAVITYMON
  }
  get isGravitymonGw() {
    return this._deviceType === DEVICE_TYPE_GRAVITYMON_GW
  }
  get isPressuremon() {
    return this._deviceType === DEVICE_TYPE_PRESSUREMON
  }
  get isIspindel() {
    return this._deviceType === DEVICE_TYPE_ISPINDEL
  }
  get isKegmon() {
    return this._deviceType === DEVICE_TYPE_KEGMON
  }
  get isChamber() {
    return this._deviceType === DEVICE_TYPE_CHAMBER_CONTROLLER
  }

  /** Devices that ingest data via POST and therefore need a token */
  get canIngest() {
    return (
      this.isGravitymon ||
      this.isPressuremon ||
      this.isIspindel ||
      this.isGravitymonGw ||
      this.isKegmon ||
      this.isChamber
    )
  }

  /** All conditions required for a proxy fetch to succeed */
  get canFetchConfig() {
    return (
      (this.isGravitymon ||
        this.isGravitymonGw ||
        this.isPressuremon ||
        this.isKegmon ||
        this.isChamber) &&
      !this.isIspindel &&
      this._url.length > 7 &&
      /^[0-9a-f]{6}$/i.test(this._chipId)
    )
  }

  /** Devices that support log collection (iSpindel cannot collect logs) */
  get canCollectLogs() {
    return !this.isIspindel
  }

}
