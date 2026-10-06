/*
 * Precompile the backup/restore JSON schemas into standalone validator modules.
 *
 * Why this exists: ajv's `compile()` builds its validator by generating JavaScript
 * source and handing it to `new Function`. That is `eval` as far as a browser is
 * concerned, so under the app's Content-Security-Policy (`script-src 'self'`, no
 * `'unsafe-eval'`) it throws EvalError and the whole restore
 * path dies before it reads a single batch.
 *
 * ajv's standalone mode does the same codegen here, at build time, and writes plain
 * modules the bundler treats like any other source file. No runtime codegen, so the
 * CSP stays strict — relaxing it to `'unsafe-eval'` for the entire app would be a far
 * worse trade than a build step.
 *
 * Run automatically by the `predev` / `prebuild` / `pretest:unit` npm hooks. Output is
 * gitignored and always regenerated, so it cannot drift from the schemas.
 */
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import Ajv from 'ajv/dist/2020.js'
import standaloneCode from 'ajv/dist/standalone/index.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const API_DIR = resolve(HERE, '../../api/oss')
const OUT_DIR = resolve(HERE, '../src/modules/backup/generated')

const readSchema = (name) => JSON.parse(readFileSync(resolve(API_DIR, name), 'utf8'))

/*
 * A producer schema and a consumer schema are not the same schema.
 *
 * The full schema says what this codebase must *write*: every key present, no unknown
 * fields. Applied to a file being *read*, two of those rules would refuse files that
 * restore perfectly well:
 *
 * - `required` — a backup written before a field existed is missing it.
 * - `unevaluatedProperties`/`additionalProperties: false` — a backup written by a
 *   *newer* build carries a field this one has never heard of.
 *
 * What is worth refusing is a wrong *type*, because that corrupts silently: a gravity
 * of `"1.010"` reads fine to a human and computes wrong.
 *
 * `if` subschemas are left alone: their `required` is a *condition*, not a constraint.
 * Stripping it makes every branch match at once.
 *
 * Same transform, same point in the pipeline as the runtime check in
 * validateDocument.ts — just earlier, at build time instead of on each restore.
 */
function relaxForImport(node, insideIf = false) {
  if (Array.isArray(node)) return node.map((n) => relaxForImport(n, insideIf))
  if (node === null || typeof node !== 'object') return node

  const out = {}
  for (const [key, value] of Object.entries(node)) {
    if (!insideIf && (key === 'required' || key === 'unevaluatedProperties')) continue
    if (!insideIf && key === 'additionalProperties' && value === false) continue
    out[key] = relaxForImport(value, insideIf || key === 'if')
  }
  return out
}

/*
 * `strict: false` because the schemas use `$ref` alongside sibling keywords, which
 * 2020-12 permits and ajv's strict mode complains about. `allErrors` so a bad file
 * reports everything wrong at once. Both bake into the generated code at build
 * time, so changing either means rebuilding, not patching the generated output.
 */
const makeAjv = () => new Ajv({ strict: false, allErrors: true, code: { source: true, esm: true } })

/*
 * ajv's standalone output pulls its runtime helpers in with CommonJS `require`, even
 * with `code.esm` set — e.g. `const func1 = require("ajv/dist/runtime/ucs2length").default`
 * for the unicode-aware minLength/maxLength check.
 *
 * `require` does not exist in a browser ES module, so the chunk throws
 * "ReferenceError: require is not defined" the moment it loads. Node-based tests never
 * see this, because there `require` resolves fine — it only appears in the browser.
 *
 * So hoist each one into a real `import`. Rewriting rather than shimming `require`
 * keeps the output statically analysable, which is what lets the bundler resolve and
 * tree-shake these helpers like any other import.
 */
function requiresToImports(code) {
  const preamble = []
  let n = 0
  const rewritten = code.replace(
    /const (\w+) = require\("([^"]+)"\)(\.default)?;/g,
    (_match, name, module, isDefault) => {
      /*
       * Add the file extension. ajv emits a deep, extensionless specifier
       * ("ajv/dist/runtime/ucs2length"); bundler resolution accepts that, but raw
       * Node ESM does not, so anything running the generated file outside Vite fails
       * with ERR_MODULE_NOT_FOUND. The explicit extension resolves in both.
       */
      const specifier = module.includes('/') && !/\.[a-z]+$/.test(module) ? `${module}.js` : module
      const tmp = `__mod${n++}`
      preamble.push(`import ${tmp} from "${specifier}";`)
      /*
       * ajv's runtime helpers are CommonJS (`exports.default = fn`), and the two
       * loaders disagree about what a default import of that is: Vite hands back the
       * function, raw Node hands back the whole `module.exports` object with the
       * function under `.default`. Picking the callable at runtime is correct under
       * both instead of betting on one.
       */
      preamble.push(
        isDefault
          ? `const ${name} = typeof ${tmp} === "function" ? ${tmp} : ${tmp}.default;`
          : `const ${name} = ${tmp};`,
      )
      return ''
    },
  )
  if (!preamble.length) return rewritten
  // After "use strict" so the directive stays first; imports hoist regardless.
  return rewritten.replace('"use strict";', `"use strict";\n${preamble.join('\n')}\n`)
}

function emit(filename, schema, description) {
  const ajv = makeAjv()
  const validate = ajv.compile(schema)
  const code = requiresToImports(standaloneCode(ajv, validate))
  writeFileSync(
    resolve(OUT_DIR, `${filename}.js`),
    `/* GENERATED — do not edit. ${description} */\n${code}`,
  )
  writeFileSync(
    resolve(OUT_DIR, `${filename}.d.ts`),
    `/* GENERATED — do not edit. */\nimport type { ValidateFunction } from 'ajv'\ndeclare const validate: ValidateFunction\nexport default validate\n`,
  )
}

mkdirSync(OUT_DIR, { recursive: true })

// Relaxed: this is the format we write, being read back. See relaxForImport above.
emit(
  'exportValidator',
  relaxForImport(readSchema('export-v1.schema.json')),
  'Compiled from api/oss/export-v1.schema.json (relaxed for import).',
)

/*
 * Compiled as authored, with NO relaxation. Relaxing it would break it: the schema is
 * an `anyOf` over a single-batch export and a backup container, and `required` is what
 * tells those two apart. Strip it and the backup branch matches any object at all, so
 * `{hello: 'world'}` validates and every type constraint below is skipped.
 */
emit(
  'brewloggerValidator',
  readSchema('brewlogger-import.schema.json'),
  'Compiled from api/oss/brewlogger-import.schema.json (as authored).',
)

console.log('Generated backup validators in src/modules/backup/generated/')
