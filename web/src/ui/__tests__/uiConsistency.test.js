import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

const appTheme = readFileSync('src/styles/app-theme.css', 'utf8')
const batchView = readFileSync('src/views/BatchView.vue', 'utf8')

const vueFiles = import.meta.glob('../../**/*.vue', {
  eager: true,
  query: '?raw',
  import: 'default'
})

describe('application-wide UI conventions', () => {
  const templates = Object.entries(vueFiles)
    .filter(([path]) => !path.includes('__tests__/'))
    .map(([path, source]) => [path, String(source)])

  it('uses the shared AppButton variant and density props instead of styling classes in views', () => {
    const violations = []
    for (const [path, source] of templates) {
      for (const match of source.matchAll(/<app-button\b([^>]*)>/gi)) {
        if (/\bclass\s*=\s*["'][^"']*\bapp-button(?:--[\w-]+)?\b/i.test(match[1])) {
          violations.push(path)
        }
      }
    }
    expect(violations).toEqual([])
  })

  it('gives native form controls the shared native-field class or an explicit specialized treatment', () => {
    const violations = []
    for (const [path, source] of templates) {
      for (const match of source.matchAll(/<(input|textarea|select)\b([^>]*)>/gi)) {
        const attrs = match[2]
        const shared = /\bclass\s*=\s*["'][^"']*\bapp-native-input\b/i.test(attrs)
        const hiddenFile = /\btype\s*=\s*["']file["']/i.test(attrs) && /display\s*:\s*none/i.test(attrs)
        const binaryChoice = /\btype\s*=\s*["'](?:checkbox|radio)["']/i.test(attrs)
        const customBackupPicker = path.endsWith('/views/BackupView.vue') && /backup-file-picker__input/.test(attrs)
        if (!shared && !hiddenFile && !binaryChoice && !customBackupPicker) violations.push(path)
      }
    }
    expect(violations).toEqual([])
  })

  it('maps Quasar page-grid gutters and dividers to the shared spacing scale', () => {
    expect(appTheme).toContain('--app-space-inline: 12px')
    expect(appTheme).toContain('--app-space-stack: 12px')
    expect(appTheme).toContain('--app-space-divider: 16px')
    expect(appTheme).toContain('--app-space-section: 24px')

    for (const size of ['sm', 'md', 'lg']) {
      expect(appTheme).toContain(`.app-page .row.q-col-gutter-${size}`)
    }

    expect(appTheme).toContain('.app-page hr {')
    expect(appTheme).toContain('margin: var(--app-space-divider) 0')
  })

  it('spaces the Batch notes divider from the form only while the split layout is active', () => {
    expect(batchView).toContain('.batch-editor-layout__main {\n  padding-right: var(--app-space-inline)')
    expect(batchView).toContain('@media (max-width: 1023px)')
    expect(batchView).toContain('.batch-editor-layout__main {\n    padding-right: 0')
  })
})
