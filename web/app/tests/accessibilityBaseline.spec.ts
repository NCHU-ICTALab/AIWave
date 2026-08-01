// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/main.css'), 'utf8')

const residentRoutes = ['/user', '/user/services', '/user/orders', '/user/booking', '/user/calendar']

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

  it('reaches the assistant as a normal page and moves focus to its main landmark', async () => {
    const { wrapper, router } = await mountApp('/user', { attach: true })

    await wrapper.get('a[href="/user/assistant"]').trigger('click')
    // 路由採 lazy import
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('assistant'))
    await flushPromises()

    // 對話是頁面而非對話框，因此不需要焦點陷阱，只需把焦點交給主要內容
    expect(document.activeElement?.id).toBe('main-content')
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })

  it('labels the assistant conversation for screen readers', async () => {
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')
    expect(wrapper.get('[aria-label="對話內容"]').attributes('aria-live')).toBe('polite')
    expect(wrapper.findAll('h1')).toHaveLength(1)
  })

  it('announces SPA navigation by moving focus to the main landmark', async () => {
    const { router } = await mountApp('/user', { attach: true })
    await router.push('/user/services')
    await flushPromises()
    expect(document.activeElement?.id).toBe('main-content')
  })
})
