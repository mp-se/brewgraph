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

function displayNumber(value: number): string {
  return Number(value).toFixed(2).replace(/\.?0+$/, '')
}

export function formatBattery(battery: number | null | undefined,
  batteryPercent: number | null | undefined): string {
  const values: string[] = []
  if (battery != null) values.push(`${displayNumber(battery)} V`)
  if (batteryPercent != null) values.push(`${displayNumber(batteryPercent)}%`)
  return values.join(' · ')
}
