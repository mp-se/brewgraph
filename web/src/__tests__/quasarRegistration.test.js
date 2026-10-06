// Copyright (c) 2024-2026 Magnus Persson
// SPDX-License-Identifier: GPL-3.0-only
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// The app registers only the Quasar components it lists in main.ts, and the unit-test setup lists
// its own. A tag missing from main.ts renders as an inert unknown element in the browser while
// every test stays green (a menu that never opened was found that way), so check the two agree.
const src = join(__dirname, '..')

function vueFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (name === '__tests__' || name === 'node_modules') return []
    return statSync(path).isDirectory() ? vueFiles(path) : path.endsWith('.vue') ? [path] : []
  })
}

const pascal = (tag) => tag.replace(/(^|-)([a-z])/g, (_, __, c) => c.toUpperCase())

describe('Quasar components used in templates', () => {
  it('are all registered in main.ts', () => {
    const main = readFileSync(join(src, 'main.ts'), 'utf8')
    const missing = new Set()
    for (const file of vueFiles(src)) {
      const template = readFileSync(file, 'utf8').split('<script')[0]
      for (const [, tag] of template.matchAll(/<(q-[a-z-]+)/g)) {
        if (!new RegExp(`\\b${pascal(tag)}\\b`).test(main)) missing.add(`${tag} (${file.replace(src, 'src')})`)
      }
    }
    expect([...missing]).toEqual([])
  })
})
