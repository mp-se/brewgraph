/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { describe, expect, it } from 'vitest'
import {
  POUR_CHART_LIMIT,
  POUR_RANGES,
  dailyTotals,
  groupPoursByDay,
  levelSeries,
  poursInRange,
  summarizePours,
  type PourRecord
} from './pourHistory'

const STOCKHOLM = 'Europe/Stockholm'

function pour(id: string, createdAt: string, amount: number, level: number, extra = {}): PourRecord {
  return {
    id,
    createdAt,
    pourAmount: amount,
    volumeRemaining: level,
    isManual: false,
    excluded: false,
    ...extra
  }
}

describe('pour history', () => {
  it('exposes the chart limit', () => {
    expect(POUR_CHART_LIMIT).toBe(500)
  })

  it('handles empty input', () => {
    expect(levelSeries([])).toEqual([])
    expect(dailyTotals([], 'UTC')).toEqual([])
    expect(groupPoursByDay([], 'UTC')).toEqual([])
    expect(summarizePours([], 'UTC')).toEqual({
      latestLevel: null,
      totalPoured: 0,
      busiestDay: null
    })
  })

  it('handles one pour', () => {
    const p = pour('a', '2026-11-01T10:00:00Z', 0.5, 18.5)

    expect(levelSeries([p])).toEqual([
      { id: 'a', time: Date.parse('2026-11-01T10:00:00Z'), level: 18.5, pour: 0.5 }
    ])
    expect(dailyTotals([p], 'UTC')).toEqual([{ day: '2026-11-01', litres: 0.5, count: 1 }])
    expect(groupPoursByDay([p], 'UTC')).toEqual([
      { day: '2026-11-01', litres: 0.5, count: 1, pours: [p] }
    ])
    expect(summarizePours([p], 'UTC')).toEqual({
      latestLevel: 18.5,
      totalPoured: 0.5,
      busiestDay: { day: '2026-11-01', litres: 0.5, count: 1 }
    })
  })

  it('leaves excluded pours out of series, totals and summary but keeps them listed', () => {
    const kept = pour('a', '2026-11-01T10:00:00Z', 1, 19)
    const excluded = pour('b', '2026-11-01T11:00:00Z', 5, 14, { excluded: true })
    const all = [kept, excluded]

    expect(levelSeries(all).map((p) => p.id)).toEqual(['a'])
    expect(dailyTotals(all, 'UTC')).toEqual([{ day: '2026-11-01', litres: 1, count: 1 }])
    expect(summarizePours(all, 'UTC')).toEqual({
      latestLevel: 19,
      totalPoured: 1,
      busiestDay: { day: '2026-11-01', litres: 1, count: 1 }
    })
    expect(groupPoursByDay(all, 'UTC')).toEqual([
      { day: '2026-11-01', litres: 1, count: 1, pours: [excluded, kept] }
    ])
  })

  it('lists a day holding only excluded pours with zero totals and no chart bar', () => {
    const only = pour('a', '2026-11-01T10:00:00Z', 2, 18, { excluded: true })

    expect(groupPoursByDay([only], 'UTC')).toEqual([
      { day: '2026-11-01', litres: 0, count: 0, pours: [only] }
    ])
    expect(dailyTotals([only], 'UTC')).toEqual([])
    expect(summarizePours([only], 'UTC').latestLevel).toBeNull()
  })

  it('splits days at local midnight in the requested time zone', () => {
    const before = pour('a', '2026-11-01T22:59:00Z', 1, 19)
    const after = pour('b', '2026-11-01T23:01:00Z', 2, 17)

    expect(dailyTotals([before, after], STOCKHOLM)).toEqual([
      { day: '2026-11-01', litres: 1, count: 1 },
      { day: '2026-11-02', litres: 2, count: 1 }
    ])
    expect(dailyTotals([before, after], 'UTC')).toEqual([{ day: '2026-11-01', litres: 3, count: 2 }])
    expect(groupPoursByDay([before, after], STOCKHOLM).map((g) => g.day)).toEqual([
      '2026-11-02',
      '2026-11-01'
    ])
  })

  it('assigns days correctly across a daylight-saving change', () => {
    const early = pour('a', '2026-03-28T23:30:00Z', 1, 19) // 00:30 CET, 29 Mar
    const late = pour('b', '2026-03-29T21:30:00Z', 1, 18) // 23:30 CEST, 29 Mar
    const next = pour('c', '2026-03-29T22:30:00Z', 1, 17) // 00:30 CEST, 30 Mar

    expect(dailyTotals([early, late, next], STOCKHOLM)).toEqual([
      { day: '2026-03-29', litres: 2, count: 2 },
      { day: '2026-03-30', litres: 1, count: 1 }
    ])
  })

  it('gives a busiest-day tie to the later day', () => {
    const pours = [
      pour('a', '2026-11-01T10:00:00Z', 1, 19),
      pour('b', '2026-11-02T10:00:00Z', 1, 18)
    ]

    expect(summarizePours(pours, 'UTC').busiestDay?.day).toBe('2026-11-02')
  })

  it('orders unsorted input and breaks time ties by id', () => {
    const pours = [
      pour('c', '2026-11-01T12:00:00Z', 1, 17),
      pour('b', '2026-11-01T10:00:00Z', 1, 18),
      pour('a', '2026-11-01T10:00:00Z', 1, 19)
    ]

    expect(levelSeries(pours).map((p) => p.id)).toEqual(['a', 'b', 'c'])
    expect(groupPoursByDay(pours, 'UTC')[0].pours.map((p) => p.id)).toEqual(['c', 'b', 'a'])
    expect(summarizePours(pours, 'UTC').latestLevel).toBe(17)
  })

  it('falls back to UTC for an invalid time zone', () => {
    const p = pour('a', '2026-11-01T23:30:00Z', 1, 19)

    expect(dailyTotals([p], 'Not/AZone')).toEqual([{ day: '2026-11-01', litres: 1, count: 1 }])
    expect(groupPoursByDay([p], '')[0].day).toBe('2026-11-01')
  })

  it('ignores negative and non-finite amounts in sums but keeps them in the list', () => {
    const good = pour('a', '2026-11-01T10:00:00Z', 1, 19)
    const negative = pour('b', '2026-11-01T11:00:00Z', -3, 19)
    const broken = pour('c', '2026-11-01T12:00:00Z', Number.NaN, 19)
    const all = [good, negative, broken]

    expect(dailyTotals(all, 'UTC')[0].litres).toBe(1)
    expect(summarizePours(all, 'UTC').totalPoured).toBe(1)
    expect(levelSeries(all).map((p) => p.pour)).toEqual([1, 0, 0])
    expect(groupPoursByDay(all, 'UTC')[0].pours).toHaveLength(3)
  })

  it('reads a timestamp without an offset as UTC and skips an unparsable one', () => {
    const naive = pour('a', '2026-11-01T23:30:00', 1, 19)
    const bad = pour('b', 'not a date', 1, 18)

    expect(dailyTotals([naive, bad], STOCKHOLM)).toEqual([
      { day: '2026-11-02', litres: 1, count: 1 }
    ])
    expect(groupPoursByDay([naive, bad], 'UTC')[0].pours).toEqual([naive])
  })
})

describe('poursInRange', () => {
  const HOUR = 3600000
  const at = (hoursAfter: number) => new Date(Date.parse('2026-11-01T00:00:00Z') + hoursAfter * HOUR).toISOString()

  it('lists the ranges the charts offer', () => {
    expect(POUR_RANGES.map((r) => [r.label, r.hours])).toEqual([
      ['6h', 6],
      ['24h', 24],
      ['7d', 168],
      ['30d', 720],
      ['All', null]
    ])
  })

  it('returns every pour, valid or not, for a null window', () => {
    const all = [pour('a', at(0), 1, 19), pour('b', 'not a date', 1, 18)]

    expect(poursInRange(all, null)).toEqual(all)
  })

  it('includes the start instant of the window and leaves out anything older', () => {
    const edge = pour('edge', at(14), 1, 18)
    const older = pour('older', new Date(Date.parse(at(14)) - 1).toISOString(), 1, 19)
    const newest = pour('newest', at(20), 1, 17)

    expect(poursInRange([older, edge, newest], 6).map((p) => p.id)).toEqual(['edge', 'newest'])
  })

  it('ends the window at the newest pour that is not excluded', () => {
    const early = pour('early', at(0), 1, 19)
    const late = pour('late', at(10), 1, 18)
    const excludedNewest = pour('x', at(100), 5, 13, { excluded: true })

    expect(poursInRange([early, late, excludedNewest], 6).map((p) => p.id)).toEqual(['late'])
  })

  it('keeps an excluded pour that lies inside the window', () => {
    const kept = pour('a', at(10), 1, 19)
    const excluded = pour('x', at(8), 5, 14, { excluded: true })

    expect(poursInRange([kept, excluded], 6).map((p) => p.id)).toEqual(['a', 'x'])
  })

  it('ends at the newest pour of any kind when every pour is excluded', () => {
    const old = pour('old', at(0), 1, 19, { excluded: true })
    const recent = pour('recent', at(10), 1, 18, { excluded: true })

    expect(poursInRange([old, recent], 6).map((p) => p.id)).toEqual(['recent'])
  })

  it('returns nothing for empty input', () => {
    expect(poursInRange([], 6)).toEqual([])
    expect(poursInRange([], null)).toEqual([])
  })

  it('keeps the input order of unsorted pours', () => {
    const pours = [pour('c', at(12), 1, 17), pour('a', at(10), 1, 19), pour('b', at(11), 1, 18)]

    expect(poursInRange(pours, 6).map((p) => p.id)).toEqual(['c', 'a', 'b'])
  })

  it('drops a pour with an unparsable timestamp when a window applies', () => {
    const good = pour('a', at(10), 1, 19)
    const bad = pour('b', 'not a date', 1, 18)

    expect(poursInRange([bad, good], 6).map((p) => p.id)).toEqual(['a'])
    expect(poursInRange([bad], 6)).toEqual([])
  })
})
