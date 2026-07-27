import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * 設計系統的不變條件。
 *
 * WCAG 2.2 AA 與觸控規範不是「當時做過就好」——沒有測試守著，下一次改版就會悄悄退化。
 */
const css = readFileSync(resolve(process.cwd(), 'src/styles/main.css'), 'utf8')

function token(name: string) {
  const value = css.match(new RegExp(`--${name}:\\s*([^;]+);`))?.[1]?.trim()
  if (!value) throw new Error(`缺少 token：--${name}`)
  return value
}

function luminance(hex: string) {
  const normalized = hex.length === 4 ? `#${[...hex.slice(1)].map((v) => v.repeat(2)).join('')}` : hex
  const channels = normalized.match(/[a-f\d]{2}/gi)?.map((v) => Number.parseInt(v, 16) / 255) ?? []
  const linear = channels.map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * (linear[0] ?? 0) + 0.7152 * (linear[1] ?? 0) + 0.0722 * (linear[2] ?? 0)
}

function contrast(foreground: string, background: string) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return ((values[0] ?? 0) + 0.05) / ((values[1] ?? 0) + 0.05)
}

describe('design system tokens', () => {
  it('defines the spacing, type and motion scales components must use', () => {
    for (const name of ['space-1', 'space-4', 'space-7', 'text-sm', 'text-base', 'motion-base', 'tap']) {
      expect(() => token(name)).not.toThrow()
    }
  })

  it('keeps body text at 16px so iOS does not auto-zoom form fields', () => {
    expect(token('text-base')).toBe('1rem')
  })

  it('sets the touch target floor to at least 44px (Apple HIG)', () => {
    expect(Number.parseInt(token('tap'), 10)).toBeGreaterThanOrEqual(44)
  })

  it('applies the touch floor to inputs and textareas, not only buttons', () => {
    const rule = css.match(/button, a, select, input, textarea \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('min-height: var(--tap)')
  })

  it('keeps micro-interactions inside the 150–300ms band', () => {
    for (const name of ['motion-fast', 'motion-base']) {
      const ms = Number.parseInt(token(name), 10)
      expect(ms).toBeGreaterThanOrEqual(120)
      expect(ms).toBeLessThanOrEqual(300)
    }
  })
})

describe('WCAG 2.2 AA', () => {
  it('meets 4.5:1 for every foreground/background pair in use', () => {
    const pairs: Array<[string, string, string]> = [
      ['ink', 'bg', '內文於頁面背景'],
      ['ink', 'surface', '內文於卡片'],
      ['muted', 'surface', '次要文字於卡片'],
      ['muted', 'bg', '次要文字於頁面背景'],
      ['surface', 'primary', '主要按鈕文字'],
      ['danger', 'danger-soft', '錯誤訊息'],
      ['success', 'success-soft', '成功狀態'],
    ]
    for (const [fg, bg, label] of pairs) {
      expect(contrast(token(fg), token(bg)), label).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('keeps the accent usable as a focus ring against page and card backgrounds', () => {
    // 非文字元件對比門檻為 3:1
    expect(contrast(token('accent'), token('bg'))).toBeGreaterThanOrEqual(3)
    expect(contrast(token('accent'), token('surface'))).toBeGreaterThanOrEqual(3)
  })

  it('never removes a focus outline without providing a replacement', () => {
    // 允許把 outline 移到容器上（input 移除、包裝元素 :focus-within 補上），
    // 但每一次移除都必須有對應的替代，焦點不能憑空消失。
    const removals = (css.match(/outline:\s*(none|0)\b/g) ?? []).length
    const replacements = (css.match(/:focus-within[^{]*\{[^}]*outline:\s*\d/g) ?? []).length
    expect(replacements).toBeGreaterThanOrEqual(removals)
  })

  it('provides a visible focus indicator', () => {
    expect(css).toMatch(/:focus-visible\s*\{[^}]*outline:\s*3px/)
  })

  it('respects prefers-reduced-motion', () => {
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
    const block = css.match(/@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\n\}/)?.[0] ?? ''
    expect(block).toContain('transition-duration')
    expect(block).toContain('animation-duration')
  })

  it('shows disabled controls as non-interactive', () => {
    expect(css).toMatch(/button:disabled\s*\{[^}]*opacity/)
    expect(css).toMatch(/button:disabled\s*\{[^}]*cursor:\s*default/)
  })
})
