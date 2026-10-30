import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const healthResponse = {
  status: 'ok',
  storage: 'ready',
  service: 'supportrecall',
}

function response(body: typeof healthResponse) {
  return {
    ok: true,
    json: async () => body,
  }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('SupportRecall application shell', () => {
  it('shows Persian navigation and confirms the real API path after connecting', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(healthResponse))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(await screen.findByRole('status')).toHaveTextContent('سرور متصل است')
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/health')
    expect(screen.getByRole('navigation', { name: 'ناوبری اصلی' })).toBeInTheDocument()
  })

  it('shows an offline state and retries the backend when requested', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(response(healthResponse))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('ارتباط با سرور برقرار نشد')
    fireEvent.click(within(status).getByRole('button', { name: 'تلاش دوباره' }))

    await waitFor(() => expect(status).toHaveTextContent('سرور متصل است'))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('switches navigation views instead of leaving placeholder controls inert', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(healthResponse)))

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'دانش‌ها' }))

    expect(screen.getByRole('heading', { name: 'مدیریت دانش' })).toBeInTheDocument()
  })
})
