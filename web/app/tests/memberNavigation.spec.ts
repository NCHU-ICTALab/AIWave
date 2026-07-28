// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('member primary navigation', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
    stubCatalogFetch()
  })

  it('shows the five approved member destinations in their reading order', async () => {
    const { wrapper } = await mountApp('/user')
    const links = wrapper.get('nav[aria-label="主要導覽"]').findAll('a')

    expect(links.map((link) => link.text().trim())).toEqual([
      '首頁',
      '點數兌換',
      'AI',
      '服務',
      '會員中心',
    ])
    expect(links.map((link) => link.attributes('href'))).toEqual([
      '/user',
      '/user/points',
      '/user/assistant',
      '/user/services',
      '/user/member',
    ])
  })
})
