import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
    expect(await screen.findByText('ذخیره‌سازی آماده است')).toBeInTheDocument()
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
    expect(await screen.findByText('وضعیت ذخیره‌سازی نامشخص است')).toBeInTheDocument()
    expect(screen.queryByText('ذخیره‌سازی آماده است')).not.toBeInTheDocument()
    fireEvent.click(within(status).getByRole('button', { name: 'تلاش دوباره' }))

    await waitFor(() => expect(status).toHaveTextContent('سرور متصل است'))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('keeps storage unconfirmed while the health request is pending', async () => {
    let resolveHealth: (value: ReturnType<typeof response>) => void = () => {
      throw new Error('health response was not requested')
    }
    const pendingHealth = new Promise<ReturnType<typeof response>>((resolve) => {
      resolveHealth = resolve
    })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pendingHealth))

    render(<App />)

    expect(screen.getByText('در حال بررسی ذخیره‌سازی')).toBeInTheDocument()
    expect(screen.queryByText('ذخیره‌سازی آماده است')).not.toBeInTheDocument()

    await act(async () => {
      resolveHealth(response(healthResponse))
      await pendingHealth
    })

    expect(await screen.findByText('ذخیره‌سازی آماده است')).toBeInTheDocument()
  })

  it('switches navigation views instead of leaving placeholder controls inert', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(healthResponse)))

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'دانش‌ها' }))

    expect(screen.getByRole('heading', { name: 'مدیریت دانش' })).toBeInTheDocument()
  })
})
