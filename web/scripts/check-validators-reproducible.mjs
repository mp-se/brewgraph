/*
 * CI reproducibility check for build-validators.mjs.
 *
 * `src/modules/backup/generated/` is gitignored on the premise that it is a
 * pure function of `api/oss/*.schema.json` plus build-validators.mjs itself
 * — regenerated on every dev/build/test run, so nothing ever needs to commit
 * it. That premise is untested: nothing confirms that what is
 * actually sitting in `generated/` at any given moment (built earlier in the
 * same CI job, left over from a previous local run, or hand-edited despite
 * the "GENERATED — do not edit" header) still matches what regenerating from
 * the current schema source produces right now.
 *
 * This script closes that gap: snapshot whatever is currently in
 * `generated/`, regenerate it from scratch, and diff the two. A mismatch
 * means the schema and the compiled validators have drifted apart — exactly
 * the failure mode "gitignored because it's reproducible" is supposed to
 * make impossible.
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = resolve(HERE, '../src/modules/backup/generated')
const BUILD_SCRIPT = resolve(HERE, 'build-validators.mjs')

function snapshot(dir) {
  if (!existsSync(dir)) return {}
  const files = {}
  for (const name of readdirSync(dir).sort()) {
    files[name] = readFileSync(join(dir, name), 'utf8')
  }
  return files
}

function diff(before, after) {
  const names = new Set([...Object.keys(before), ...Object.keys(after)])
  const problems = []
  for (const name of [...names].sort()) {
    if (!(name in before)) {
      problems.push(`  + ${name} (regeneration produced a file that wasn't there before)`)
    } else if (!(name in after)) {
      problems.push(`  - ${name} (regeneration no longer produces this file)`)
    } else if (before[name] !== after[name]) {
      problems.push(`  ~ ${name} (content differs from a fresh regeneration)`)
    }
  }
  return problems
}

const before = snapshot(OUT_DIR)
if (Object.keys(before).length === 0) {
  console.error(
    'check-validators-reproducible: generated/ is empty or missing — run ' +
      '`npm run build:validators` first so there is something to compare against.',
  )
  process.exit(1)
}

// Regenerate in place — build-validators.mjs's emit() overwrites each named
// file via writeFileSync, so this is exactly what `npm run build:validators`
// does on its own; nothing here is scratch/throwaway.
execFileSync(process.execPath, [BUILD_SCRIPT], { stdio: 'inherit' })
const after = snapshot(OUT_DIR)

const problems = diff(before, after)
if (problems.length > 0) {
  console.error(
    'check-validators-reproducible: FAILED — regenerating the validators from ' +
      'api/oss/*.schema.json produced different output than what was previously in ' +
      'src/modules/backup/generated/:\n' +
      problems.join('\n') +
      '\n\nThis means whatever built src/modules/backup/generated/ earlier did not ' +
      'reflect the current schema source, or a generated file was hand-edited. ' +
      'Run `npm run build:validators` and investigate why the two runs disagree.',
  )
  process.exit(1)
}

console.log(
  `check-validators-reproducible: OK — ${Object.keys(before).length} generated file(s) match a fresh regeneration.`,
)
