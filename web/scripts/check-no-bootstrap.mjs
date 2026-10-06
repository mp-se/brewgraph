import { readFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'

const forbidden = /^(?:btn(?:-.+)?|badge|bg-(?:primary|secondary|success|warning|danger|info)|text-bg-.+|alert(?:-.+)?|table(?:-.+)?|form-(?:control|select|check|label|text|switch)|input-group(?:-.+)?|modal(?:-.+)?|container(?:-.+)?|d-flex|(?:align-items|justify-content)-.+|(?:m|p)[trblxy]?-[0-9]+|(?:m|p)[se]-[0-9]+|fw-.+|fs-.+|spinner-border(?:-.+)?|progress(?:-.+)?|list-group(?:-.+)?|page-(?:item|link)|pagination|bi(?:-.+)?)$/

async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  return (await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return entry.name === '__tests__' ? [] : files(path)
    return /\.(?:vue|ts)$/.test(entry.name) ? [path] : []
  }))).flat()
}

const failures = []
for (const file of await files(new URL('../src/', import.meta.url).pathname)) {
  const source = await readFile(file, 'utf8')
  if (/(?:bootstrap|data-bs-|bi-)/i.test(source)) failures.push(`${file}: Bootstrap reference`)
  for (const match of source.matchAll(/(?:^|\s):?class="([^"]*)"/gm)) {
    for (const token of match[1].match(/[\w-]+/g) ?? []) {
      if (forbidden.test(token)) failures.push(`${file}: Bootstrap class ${token}`)
    }
  }
}

const packageJson = await readFile(new URL('../package.json', import.meta.url), 'utf8')
if (/"bootstrap(?:-icons)?"/.test(packageJson)) failures.push('package.json: Bootstrap dependency')
if (failures.length) {
  console.error(failures.join('\n'))
  process.exit(1)
}
