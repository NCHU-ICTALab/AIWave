// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/main.css'), 'utf8')

const residentRoutes = ['/user', '/user/services', '/user/orders']

function luminance(hex: string) {
  const normalized = hex.length === 4 ? `#${[...hex.slice(1)].map((value) => value.repeat(2)).join('')}` : hex
  const channels = normalized.match(/[a-f\d]{2}/gi)?.map((value) => Number.parseInt(value, 16) / 255) ?? []
  const linear = channels.map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))
  return 0.2126 * (linear[0] ?? 0) + 0.7152 * (linear[1] ?? 0) + 0.0722 * (linear[2] ?? 0)
}

function contrast(foreground: string, background: string) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return ((values[0] ?? 0) + 0.05) / ((values[1] ?? 0) + 0.05)
}

function token(name: string) {
  const value = styles.match(new RegExp(`--${name}:\\s*(#[a-f\\d]{3}(?:[a-f\\d]{3})?)`, 'i'))?.[1]
  if (!value) throw new Error(`Missing CSS color token: ${name}`)
  return value
}

describe('WCAG AA baseline', () => {
  beforeEach(() => stubCatalogFetch())

  it('keeps primary text combinations above the 4.5:1 normal-text threshold', () => {
    expect(contrast(token('ink'), token('bg'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('muted'), token('surface'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('surface'), token('primary'))).toBeGreaterThanOrEqual(4.5)
  })

  it('gives the sign-in page a single heading and a focusable main landmark', async () => {
    const { wrapper } = await mountApp('/login', { identity: null })
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('main').attributes('id')).toBe('main-content')
  })

  it.each(residentRoutes)('provides landmarks, a page heading, and named navigation at %s', async (path) => {
    const { wrapper } = await mountApp(path)

    expect(wrapper.get('main').attributes('id')).toBe('main-content')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('主要導覽')
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('.skip-link').attributes('href')).toBe('#main-content')
  })

  it('moves focus into the Copilot dialog, closes on Escape, and returns focus', async () => {
    const { wrapper } = await mountApp('/user', { attach: true })
    const opener = wrapper.get('[aria-haspopup="dialog"]')
    ;(opener.element as HTMLElement).focus()
    await opener.trigger('click')
    await flushPromises()

    expect(document.activeElement?.getAttribute('aria-label')).toBe('關閉生活管家')
    document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(document.querySelector('[aria-labelledby="copilot-title"]')).toBeNull()
    expect(document.activeElement).toBe(opener.element)
  })

  it('announces SPA navigation by moving focus to the main landmark', async () => {
    const { router } = await mountApp('/user', { attach: true })
    await router.push('/user/services')
    await flushPromises()
    expect(document.activeElement?.id).toBe('main-content')
  })
})
