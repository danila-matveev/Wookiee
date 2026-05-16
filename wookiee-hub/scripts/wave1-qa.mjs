#!/usr/bin/env node
// Wave 1 QA — full Playwright sweep, 38 routes × 2 themes = 76 cells.
// Transient: playwright installed --no-save, удалить после.
// Reads HUB_QA_USER_PASSWORD из ../.env (repo root).

import { chromium } from 'playwright'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = join(__dirname, '..', '..')
const HUB_DIR = join(__dirname, '..')
const SCREENSHOTS_DIR = join(HUB_DIR, 'wave1-qa-screenshots')
const REPORT_PATH = join(REPO_ROOT, 'docs', 'superpowers', 'plans', 'wave1', 'WAVE1_QA_REPORT.md')

// Read password from repo root .env
const envText = readFileSync(join(REPO_ROOT, '.env'), 'utf-8')
const pwMatch = envText.match(/^HUB_QA_USER_PASSWORD=(.+)$/m)
if (!pwMatch) throw new Error('HUB_QA_USER_PASSWORD not in .env')
const QA_PASSWORD = pwMatch[1].trim()
const QA_EMAIL = 'claude-agent@wookiee.shop'
const BASE_URL = 'http://localhost:5173'

if (!existsSync(SCREENSHOTS_DIR)) mkdirSync(SCREENSHOTS_DIR, { recursive: true })

const routes = [
  // public
  { path: '/login', group: 'login', protected: false },
  // hub-shell (protected)
  { path: '/operations/tools', group: 'hub-shell' },
  { path: '/operations/activity', group: 'hub-shell' },
  { path: '/operations/health', group: 'hub-shell' },
  { path: '/community/reviews', group: 'hub-shell' },
  { path: '/community/questions', group: 'hub-shell' },
  { path: '/community/answers', group: 'hub-shell' },
  { path: '/community/analytics', group: 'hub-shell' },
  { path: '/influence/bloggers', group: 'hub-shell' },
  { path: '/influence/integrations', group: 'hub-shell' },
  { path: '/influence/calendar', group: 'hub-shell' },
  { path: '/analytics/rnp', group: 'hub-shell' },
  // preview
  { path: '/design-system-preview', group: 'preview' },
  // catalog (22)
  { path: '/catalog/matrix', group: 'catalog' },
  { path: '/catalog/colors', group: 'catalog' },
  { path: '/catalog/artikuly', group: 'catalog' },
  { path: '/catalog/tovary', group: 'catalog' },
  { path: '/catalog/skleyki', group: 'catalog' },
  { path: '/catalog/semeystva-cvetov', group: 'catalog' },
  { path: '/catalog/upakovki', group: 'catalog' },
  { path: '/catalog/kanaly-prodazh', group: 'catalog' },
  { path: '/catalog/sertifikaty', group: 'catalog' },
  { path: '/catalog/import', group: 'catalog' },
  { path: '/catalog/__demo__', group: 'catalog' },
  { path: '/catalog/references/kategorii', group: 'catalog' },
  { path: '/catalog/references/kollekcii', group: 'catalog' },
  { path: '/catalog/references/tipy-kollekciy', group: 'catalog' },
  { path: '/catalog/references/brendy', group: 'catalog' },
  { path: '/catalog/references/fabriki', group: 'catalog' },
  { path: '/catalog/references/importery', group: 'catalog' },
  { path: '/catalog/references/razmery', group: 'catalog' },
  { path: '/catalog/references/statusy', group: 'catalog' },
  { path: '/catalog/references/atributy', group: 'catalog' },
  // marketing (2, behind feature flag — VITE_FEATURE_MARKETING=true)
  { path: '/marketing/promo-codes', group: 'marketing' },
  { path: '/marketing/search-queries', group: 'marketing' },
]

console.log(`[QA] ${routes.length} routes × 2 themes = ${routes.length * 2} screenshots`)

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()

// Pre-attach console listener (we toggle per-route below to scope errors)
let currentErrors = []
page.on('console', (msg) => {
  if (msg.type() === 'error') currentErrors.push(msg.text())
})
page.on('pageerror', (err) => {
  currentErrors.push(`[pageerror] ${err.message}`)
})

// LOGIN flow once
console.log('[QA] login...')
await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' })
// Switch to password mode
await page.getByRole('button', { name: /войти с паролем/i }).click()
await page.fill('input[type=email]', QA_EMAIL)
await page.fill('input[type=password]', QA_PASSWORD)
await page.getByRole('button', { name: /^войти$/i }).click()
// Wait for navigation to /operations/tools (handlePassword does navigate)
try {
  await page.waitForURL(/\/operations\/tools/, { timeout: 15000 })
  console.log('[QA] login OK, session active')
} catch (e) {
  console.log('[QA] login failed or timed out — continuing; protected pages may render /login')
  console.log('[QA] current URL:', page.url())
}

const results = []

for (const route of routes) {
  for (const theme of ['light', 'dark']) {
    currentErrors = []
    // Set theme BEFORE navigation so FOWT-script picks correct theme on cold paint
    await page.evaluate((t) => {
      localStorage.setItem('wookiee-theme', JSON.stringify({ state: { theme: t }, version: 0 }))
    }, theme)
    try {
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle', timeout: 20000 })
    } catch (e) {
      currentErrors.push(`[nav-timeout] ${e.message}`)
    }
    // Extra wait for React/data render
    await page.waitForTimeout(800)

    const filenameSafe = route.path === '/' ? 'root' : route.path.slice(1).replace(/\//g, '_')
    const file = `${filenameSafe}__${theme}.png`
    try {
      await page.screenshot({ path: join(SCREENSHOTS_DIR, file), fullPage: false })
    } catch (e) {
      currentErrors.push(`[screenshot-fail] ${e.message}`)
    }

    // DOM checks
    const checks = await page.evaluate(() => {
      const body = document.body
      const computed = window.getComputedStyle(body)
      const htmlIsDark = document.documentElement.classList.contains('dark')
      const fontFamily = computed.fontFamily
      const h1 = document.querySelector('h1')
      const h1FontFamily = h1 ? window.getComputedStyle(h1).fontFamily : null
      const rootEmpty = (document.getElementById('root')?.children.length ?? 0) === 0
      return {
        url: window.location.pathname,
        htmlIsDark,
        bodyFontFamily: fontFamily,
        h1FontFamily,
        rootEmpty,
        title: document.title,
      }
    })

    results.push({
      route: route.path,
      group: route.group,
      theme,
      file,
      errors: [...currentErrors],
      htmlIsDark: checks.htmlIsDark,
      themeMatchesUrl: checks.htmlIsDark === (theme === 'dark'),
      bodyFontHasDmSans: /DM Sans/i.test(checks.bodyFontFamily),
      h1FontHasInstrumentSerif: checks.h1FontFamily ? /Instrument Serif/i.test(checks.h1FontFamily) : null,
      rootRendered: !checks.rootEmpty,
      actualUrl: checks.url,
    })
    process.stdout.write('.')
  }
}
console.log('')

await browser.close()

// Generate WAVE1_QA_REPORT.md
const totals = {
  cells: results.length,
  rendered: results.filter(r => r.rootRendered).length,
  errors: results.reduce((s, r) => s + r.errors.length, 0),
  cellsWithErrors: results.filter(r => r.errors.length > 0).length,
  themeMismatches: results.filter(r => !r.themeMatchesUrl).length,
  dmSansBody: results.filter(r => r.bodyFontHasDmSans).length,
  instrumentSerifH1: results.filter(r => r.h1FontHasInstrumentSerif === true).length,
  h1Present: results.filter(r => r.h1FontHasInstrumentSerif !== null).length,
}

const byGroup = {}
for (const r of results) {
  byGroup[r.group] ??= { total: 0, ok: 0, errors: 0 }
  byGroup[r.group].total++
  if (r.rootRendered && r.errors.length === 0) byGroup[r.group].ok++
  byGroup[r.group].errors += r.errors.length
}

const lines = []
lines.push('# Wave 1 — QA Report (Playwright sweep)')
lines.push('')
lines.push(`**Дата:** 2026-05-16`)
lines.push(`**Branch:** \`feat/ds-v2-wave-1-spec\``)
lines.push(`**Routes × Themes:** ${routes.length} × 2 = ${routes.length * 2} cells`)
lines.push(`**Screenshots:** \`wookiee-hub/wave1-qa-screenshots/*.png\` (gitignored)`)
lines.push('')
lines.push('---')
lines.push('')
lines.push('## Totals')
lines.push('')
lines.push(`- Cells total: ${totals.cells}`)
lines.push(`- Rendered (root mounted, no blank screen): ${totals.rendered} / ${totals.cells}`)
lines.push(`- Cells with console/page errors: ${totals.cellsWithErrors}`)
lines.push(`- Total error count: ${totals.errors}`)
lines.push(`- Theme matches URL setting: ${totals.cells - totals.themeMismatches} / ${totals.cells}`)
lines.push(`- Body font has DM Sans: ${totals.dmSansBody} / ${totals.cells}`)
lines.push(`- H1 has Instrument Serif: ${totals.instrumentSerifH1} / ${totals.h1Present} (h1 присутствует)`)
lines.push('')
lines.push('## По группам')
lines.push('')
lines.push('| Группа | Cells | Clean | Errors |')
lines.push('|---|---|---|---|')
for (const [g, t] of Object.entries(byGroup)) {
  lines.push(`| ${g} | ${t.total} | ${t.ok} | ${t.errors} |`)
}
lines.push('')
lines.push('## Per-route pass/fail')
lines.push('')
lines.push('| Route | Theme | Errors | Rendered | Theme OK | DM Sans | Instrument Serif h1 |')
lines.push('|---|---|---|---|---|---|---|')
for (const r of results) {
  const errs = r.errors.length === 0 ? '0' : `**${r.errors.length}**`
  const rendered = r.rootRendered ? '✅' : '❌'
  const themeOk = r.themeMatchesUrl ? '✅' : '❌'
  const dm = r.bodyFontHasDmSans ? '✅' : '⚠️'
  const inst = r.h1FontHasInstrumentSerif === null ? '—' : (r.h1FontHasInstrumentSerif ? '✅' : '⚠️')
  lines.push(`| \`${r.route}\` | ${r.theme} | ${errs} | ${rendered} | ${themeOk} | ${dm} | ${inst} |`)
}
lines.push('')
lines.push('## Errors detail')
lines.push('')
const errorRoutes = results.filter(r => r.errors.length > 0)
if (errorRoutes.length === 0) {
  lines.push('Нет ошибок — все 76 cells без console/page errors.')
} else {
  for (const r of errorRoutes) {
    lines.push(`### \`${r.route}\` [${r.theme}]`)
    for (const e of r.errors) lines.push(`- ${e.slice(0, 500)}`)
    lines.push('')
  }
}
lines.push('')
lines.push('## Methodology')
lines.push('')
lines.push('- Playwright локально установлен `--no-save` (transient, удалён после QA — spec 3.10 fallback)')
lines.push('- Dev server: `npm run dev` на localhost:5173')
lines.push('- Login: claude-agent@wookiee.shop через password mode (Supabase signInWithPassword)')
lines.push('- Theme switch: `localStorage.setItem("wookiee-theme", JSON.stringify({state:{theme},version:0}))` перед каждой navigation → FOWT script на cold paint берёт правильную тему')
lines.push('- Screenshots: 1440×900 viewport, viewport-only (не fullPage)')
lines.push('- Console errors собираются через `page.on("console")` + page-errors через `page.on("pageerror")`')
lines.push('- DOM checks per cell: `html.dark` class, `body` font-family, `h1` font-family, root mounted')
lines.push('')
lines.push(`*Wave 1 QA Playwright sweep · 2026-05-16 · ${totals.cells} cells*`)
lines.push('')

writeFileSync(REPORT_PATH, lines.join('\n'))
console.log(`[QA] report → ${REPORT_PATH}`)
console.log(`[QA] screenshots → ${SCREENSHOTS_DIR}`)
console.log(`[QA] totals:`, totals)
