import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  if (typeof document !== 'undefined') {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new Error('Network is disabled unless this test provides a fetch contract')))
  }
})

afterEach(() => {
  if (typeof document !== 'undefined') {
    document.body.innerHTML = ''
  }
  vi.unstubAllGlobals()
})
