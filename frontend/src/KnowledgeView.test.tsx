import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import KnowledgeView from './KnowledgeView'

const readySource = {
  id: 'source-ready',
  filename: 'گفتگوهای-پشتیبانی.csv',
  format: 'csv',
  status: 'ready',
  record_count: 1,
  error_code: null,
  error_message: null,
  retryable: false,
  created_at: '2026-10-29T10:00:00+00:00',
  updated_at: '2026-10-29T10:00:00+00:00',
}

const failedSource = {
  ...readySource,
  id: 'source-failed',
  filename: 'ورود-ناموفق.json',
  status: 'failed',
  error_code: 'import_interrupted',
  error_message: 'ورود منبع متوقف شد. دوباره تلاش کنید.',
  retryable: true,
}

function response(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Persian knowledge import workflow', () => {
  it('shows Persian guidance, downloadable samples, and the empty library state', async () => {
    let resolveSources: (value: ReturnType<typeof response>) => void = () => {
      throw new Error('source response was not requested')
    }
    const pendingSources = new Promise<ReturnType<typeof response>>((resolve) => {
      resolveSources = resolve
    })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pendingSources))

    render(<KnowledgeView />)

    expect(screen.getByRole('status')).toHaveTextContent('در حال دریافت فهرست منابع')
    await act(async () => {
      resolveSources(response([]))
      await pendingSources
    })
    expect(await screen.findByText('هنوز منبعی وارد نشده است')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'دانلود نمونه CSV' })).toHaveAttribute(
      'href',
      '/samples/نمونه-پشتیبانی.csv',
    )
    expect(screen.getByRole('link', { name: 'دانلود نمونه JSON' })).toHaveAttribute(
      'href',
      '/samples/نمونه-پشتیبانی.json',
    )
    expect(screen.getByRole('link', { name: 'دانلود نمونه متن' })).toHaveAttribute(
      'href',
      '/samples/نمونه-پشتیبانی.txt',
    )
    expect(screen.getByText(/CSV، JSON و متن ساده/)).toBeInTheDocument()
  })

  it('maps Persian CSV columns, previews, imports, refreshes the list, and inspects records', async () => {
    const preview = {
      format: 'csv',
      columns: ['پرسش مشتری', 'پاسخ پشتیبانی'],
      needs_mapping: false,
      record_count: 1,
      records: [
        {
          conversation_id: 'پشتیبانی-نمونه-۰۰۱',
          date: '2026-10-20',
          product: 'پرداخت',
          category: 'بازگشت وجه',
          messages: [
            { role: 'customer', content: 'مبلغ پرداخت دوبار کم شده است.' },
            { role: 'support', content: 'مبلغ اضافی طی دو روز کاری برمی‌گردد.' },
          ],
        },
      ],
    }
    const details = {
      source: readySource,
      records: [
        {
          position: 1,
          conversation_id: 'پشتیبانی-نمونه-۰۰۱',
          date: '2026-10-20',
          product: 'پرداخت',
          category: 'بازگشت وجه',
          messages: preview.records[0].messages,
        },
      ],
    }
    let imported = false
    let mappedPreview = false
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/sources' && (!init?.method || init.method === 'GET')) {
        return response(imported ? [readySource] : [])
      }
      if (url === '/api/sources/preview') {
        const form = init?.body as FormData
        mappedPreview = form.has('mapping_json')
        return response(mappedPreview ? preview : {
          format: 'csv',
          columns: ['پرسش مشتری', 'پاسخ پشتیبانی'],
          needs_mapping: true,
          record_count: null,
          records: [],
        })
      }
      if (url === '/api/sources/import') {
        imported = true
        return response({ source: readySource, duplicate: false })
      }
      if (url === '/api/sources/source-ready') return response(details)
      return response({ detail: 'unexpected request' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeView />)
    await screen.findByText('هنوز منبعی وارد نشده است')
    const file = new File(['پرسش مشتری,پاسخ پشتیبانی\nسؤال,پاسخ\n'], 'گفتگو.csv', {
      type: 'text/csv',
    })
    fireEvent.change(screen.getByLabelText('فایل ورودی پشتیبانی'), {
      target: { files: [file] },
    })

    expect(await screen.findByText('نگاشت ستون‌های CSV')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('ستون پرسش'), { target: { value: 'پرسش مشتری' } })
    fireEvent.change(screen.getByLabelText('ستون پاسخ'), { target: { value: 'پاسخ پشتیبانی' } })
    fireEvent.click(screen.getByRole('button', { name: 'ساخت پیش‌نمایش' }))

    expect(await screen.findByText('مبلغ پرداخت دوبار کم شده است.')).toBeInTheDocument()
    expect(screen.getByText('۱ گفت‌وگو برای ورود آماده است')).toBeInTheDocument()
    expect(mappedPreview).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'ورود به کتابخانه' }))

    expect(await screen.findByText('منبع با موفقیت وارد شد.')).toBeInTheDocument()
    const sourceRow = await screen.findByText(readySource.filename)
    expect(within(sourceRow.closest('article')!).getByText('آماده')).toBeInTheDocument()
    fireEvent.click(within(sourceRow.closest('article')!).getByRole('button', { name: 'نمایش جزئیات' }))
    expect(await screen.findByText('مبلغ اضافی طی دو روز کاری برمی‌گردد.')).toBeInTheDocument()
  })

  it('shows a Persian validation message and withholds import after an invalid preview', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === '/api/sources') return response([])
      return response({
        detail: { code: 'invalid_record', message: 'گفت‌وگو باید پرسش و پاسخ داشته باشد.' },
      }, 422)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeView />)
    await screen.findByText('هنوز منبعی وارد نشده است')
    const file = new File(['{}'], 'گفتگو.json', { type: 'application/json' })
    fireEvent.change(screen.getByLabelText('فایل ورودی پشتیبانی'), {
      target: { files: [file] },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'گفت‌وگو باید پرسش و پاسخ داشته باشد.',
    )
    expect(screen.queryByRole('button', { name: 'ورود به کتابخانه' })).not.toBeInTheDocument()
  })

  it('retries a failed source and requires Persian confirmation before deletion', async () => {
    let ready = false
    let deleted = false
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/sources' && (!init?.method || init.method === 'GET')) {
        return response(deleted ? [] : [ready ? readySource : failedSource])
      }
      if (url === '/api/sources/source-failed/retry') {
        ready = true
        return response({ source: readySource, duplicate: false })
      }
      if (url === '/api/sources/source-ready' && init?.method === 'DELETE') {
        deleted = true
        return response(null, 204)
      }
      return response({ detail: 'unexpected request' }, 404)
    })
    const confirmMock = vi.fn().mockReturnValue(false)
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('confirm', confirmMock)

    render(<KnowledgeView />)
    const sourceName = await screen.findByText(failedSource.filename)
    const failedRow = sourceName.closest('article')!
    expect(within(failedRow).getByText('ناموفق')).toBeInTheDocument()
    fireEvent.click(within(failedRow).getByRole('button', { name: 'تلاش دوباره' }))

    const readyName = await screen.findByText(readySource.filename)
    const readyRow = readyName.closest('article')!
    expect(within(readyRow).getByText('آماده')).toBeInTheDocument()
    fireEvent.click(within(readyRow).getByRole('button', { name: 'حذف منبع' }))
    expect(confirmMock).toHaveBeenCalledWith(expect.stringContaining('آیا مطمئن هستید'))
    expect(readyName).toBeInTheDocument()
    confirmMock.mockReturnValueOnce(true)
    fireEvent.click(within(readyRow).getByRole('button', { name: 'حذف منبع' }))

    await waitFor(() => expect(screen.queryByText(readySource.filename)).not.toBeInTheDocument())
    expect(await screen.findByText('هنوز منبعی وارد نشده است')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/sources/source-ready', { method: 'DELETE' })
  })
})
