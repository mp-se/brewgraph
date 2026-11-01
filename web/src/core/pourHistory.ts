/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/**
 * Framework-independent pour-history calculations for a keg: the level series,
 * per-day totals, the day-grouped list and a summary.
 *
 * Excluded pours are left out of every number and series; the grouped list still
 * carries them. A pour whose timestamp cannot be parsed has no place on a time
 * axis or in a day and is skipped. A timestamp without a UTC offset is read as UTC.
 */

export interface PourRecord {
  id: string
  /** ISO 8601 UTC. */
  createdAt: string
  /** Litres. */
  pourAmount: number
  /** Litres, the level after this pour. */
  volumeRemaining: number
  isManual: boolean
  excluded: boolean
}

export interface LevelPoint {
  id: string
  /** Epoch milliseconds. */
  time: number
  level: number
  pour: number
}

export interface DayTotal {
  /** YYYY-MM-DD in the requested time zone. */
  day: string
  litres: number
  count: number
}

export interface DayGroup {
  day: string
  litres: number
  count: number
  /** Newest first, excluded pours included. */
  pours: PourRecord[]
}

export interface PourSummary {
  latestLevel: number | null
  totalPoured: number
  busiestDay: DayTotal | null
}

/** Most recent pours the charts draw. */
export const POUR_CHART_LIMIT = 500

interface TimedPour {
  pour: PourRecord
  time: number
}

const HAS_OFFSET = /(?:Z|[+-]\d{2}(?::?\d{2})?)$/i

function parseTime(createdAt: string): number {
  const text = String(createdAt ?? '').trim()
  if (!text) return Number.NaN
  const withOffset = text.includes('T') && !HAS_OFFSET.test(text) ? text + 'Z' : text
  return new Date(withOffset).getTime()
}

/** Ascending by time, ties by id. */
function timed(pours: readonly PourRecord[]): TimedPour[] {
  return pours
    .map((pour) => ({ pour, time: parseTime(pour.createdAt) }))
    .filter((entry) => Number.isFinite(entry.time))
    .sort((a, b) => a.time - b.time || (a.pour.id < b.pour.id ? -1 : a.pour.id > b.pour.id ? 1 : 0))
}

function litresOf(pour: PourRecord): number {
  const amount = Number(pour.pourAmount)
  return Number.isFinite(amount) && amount > 0 ? amount : 0
}

const formatters = new Map<string, Intl.DateTimeFormat>()

function dayFormatter(timeZone: string): Intl.DateTimeFormat {
  let formatter = formatters.get(timeZone)
  if (!formatter) {
    const options = { year: 'numeric', month: '2-digit', day: '2-digit' } as const
    try {
      formatter = new Intl.DateTimeFormat('en-CA', { ...options, timeZone })
    } catch {
      formatter = new Intl.DateTimeFormat('en-CA', { ...options, timeZone: 'UTC' })
    }
    formatters.set(timeZone, formatter)
  }
  return formatter
}

function dayOf(time: number, timeZone: string): string {
  const parts = dayFormatter(timeZone).formatToParts(new Date(time))
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

export interface PourRange {
  label: string
  /** Window length in hours; null is every pour. */
  hours: number | null
}

export const POUR_RANGES: readonly PourRange[] = [
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 168 },
  { label: '30d', hours: 720 },
  { label: 'All', hours: null }
]

/**
 * Pours inside a window of `hours` ending at the newest pour that is not excluded (never "now");
 * hours null returns all. Pours keep their input order; excluded pours inside the window are kept;
 * pours with an unparsable timestamp are dropped when a window applies. With no non-excluded pour
 * the window ends at the newest pour of any kind.
 */
export function poursInRange(pours: readonly PourRecord[], hours: number | null): PourRecord[] {
  if (hours === null) return [...pours]
  const entries = pours
    .map((pour) => ({ pour, time: parseTime(pour.createdAt) }))
    .filter((entry) => Number.isFinite(entry.time))
  const kept = entries.filter((entry) => !entry.pour.excluded)
  const end = Math.max(...(kept.length > 0 ? kept : entries).map((entry) => entry.time))
  const start = end - hours * 3600000
  return entries.filter((entry) => entry.time >= start && entry.time <= end).map((entry) => entry.pour)
}

/** Remaining volume after each non-excluded pour, oldest first. */
export function levelSeries(pours: readonly PourRecord[]): LevelPoint[] {
  return timed(pours)
    .filter(({ pour }) => !pour.excluded && Number.isFinite(Number(pour.volumeRemaining)))
    .map(({ pour, time }) => ({
      id: pour.id,
      time,
      level: Number(pour.volumeRemaining),
      pour: litresOf(pour)
    }))
}

/** Litres and pour count per day over non-excluded pours, oldest day first; days without pours are absent. */
export function dailyTotals(pours: readonly PourRecord[], timeZone: string): DayTotal[] {
  const totals = new Map<string, DayTotal>()
  for (const { pour, time } of timed(pours)) {
    if (pour.excluded) continue
    const day = dayOf(time, timeZone)
    const total = totals.get(day) ?? { day, litres: 0, count: 0 }
    total.litres += litresOf(pour)
    total.count += 1
    totals.set(day, total)
  }
  return [...totals.values()].sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0))
}

/** Pours grouped by day, newest day and newest pour first; excluded pours are listed but not counted. */
export function groupPoursByDay(pours: readonly PourRecord[], timeZone: string): DayGroup[] {
  const groups = new Map<string, DayGroup>()
  for (const { pour, time } of timed(pours).reverse()) {
    const day = dayOf(time, timeZone)
    const group = groups.get(day) ?? { day, litres: 0, count: 0, pours: [] }
    group.pours.push(pour)
    if (!pour.excluded) {
      group.litres += litresOf(pour)
      group.count += 1
    }
    groups.set(day, group)
  }
  return [...groups.values()].sort((a, b) => (a.day < b.day ? 1 : a.day > b.day ? -1 : 0))
}

/** Latest level, total poured and busiest day over non-excluded pours. */
export function summarizePours(pours: readonly PourRecord[], timeZone: string): PourSummary {
  const series = levelSeries(pours)
  const totals = dailyTotals(pours, timeZone)
  let busiestDay: DayTotal | null = null
  for (const total of totals) {
    if (busiestDay === null || total.litres >= busiestDay.litres) busiestDay = total
  }
  return {
    latestLevel: series.length > 0 ? series[series.length - 1].level : null,
    totalPoured: totals.reduce((sum, total) => sum + total.litres, 0),
    busiestDay
  }
}
