import { strings } from './strings'

export type HealthStatus = {
  status: string
  storage: string
  service: string
}

export type CsvColumnMapping = {
  question: string
  answer: string
  conversation_id?: string | null
  date?: string | null
  product?: string | null
  category?: string | null
}

export type ImportedMessage = { role: 'customer' | 'support'; content: string }

export type ImportedConversation = {
  conversation_id: string | null
  date: string | null
  product: string | null
  category: string | null
  messages: ImportedMessage[]
}

export type SourcePreview = {
  format: 'csv' | 'json' | 'text'
  columns: string[]
  needs_mapping: boolean
  record_count: number | null
  records: ImportedConversation[]
}

export type SourceSummary = {
  id: string
  filename: string
  format: 'csv' | 'json' | 'text'
  status: 'pending' | 'processing' | 'ready' | 'failed'
  record_count: number
  error_code: string | null
  error_message: string | null
  retryable: boolean
  created_at: string
  updated_at: string
}

export type SourceImportResult = { source: SourceSummary; duplicate: boolean }

export type SourceDetail = {
  source: SourceSummary
  records: Array<ImportedConversation & { position: number }>
}

export class ApiRequestError extends Error {
  readonly code: string
  readonly status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = code
    this.status = status
  }
}

export class HealthRequestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'HealthRequestError'
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  const response = await fetch('/api/health', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    signal,
  })

  if (!response.ok) {
    throw new HealthRequestError('health_request_failed')
  }

  const payload: unknown = await response.json()
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('status' in payload) ||
    payload.status !== 'ok' ||
    !('storage' in payload) ||
    payload.storage !== 'ready' ||
    !('service' in payload) ||
    payload.service !== 'supportrecall'
  ) {
    throw new HealthRequestError('invalid_health_response')
  }

  return payload as HealthStatus
}

export async function previewSource(
  file: File,
  mapping?: CsvColumnMapping,
): Promise<SourcePreview> {
  return requestJson('/api/sources/preview', {
    method: 'POST',
    body: uploadBody(file, mapping),
  })
}

export async function importSource(
  file: File,
  mapping?: CsvColumnMapping,
): Promise<SourceImportResult> {
  return requestJson('/api/sources/import', {
    method: 'POST',
    body: uploadBody(file, mapping),
  })
}

export function fetchSources(): Promise<SourceSummary[]> {
  return requestJson('/api/sources')
}

export function fetchSourceDetail(sourceId: string): Promise<SourceDetail> {
  return requestJson(`/api/sources/${encodeURIComponent(sourceId)}`)
}

export function retrySource(sourceId: string): Promise<SourceImportResult> {
  return requestJson(`/api/sources/${encodeURIComponent(sourceId)}/retry`, { method: 'POST' })
}

export async function deleteSource(sourceId: string): Promise<void> {
  const response = await fetch(`/api/sources/${encodeURIComponent(sourceId)}`, {
    method: 'DELETE',
  })
  if (response.ok) return
  throw await apiError(response)
}

function uploadBody(file: File, mapping?: CsvColumnMapping): FormData {
  const body = new FormData()
  body.append('file', file)
  if (mapping) body.append('mapping_json', JSON.stringify(mapping))
  return body
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) throw await apiError(response)
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiRequestError(strings.knowledge.invalidResponse, 'invalid_response', response.status)
  }
}

async function apiError(response: Response): Promise<ApiRequestError> {
  try {
    const payload: unknown = await response.json()
    if (isRecord(payload) && isRecord(payload.detail)) {
      const detail = payload.detail
      const code = typeof detail.code === 'string' ? detail.code : 'request_failed'
      const message = typeof detail.message === 'string' ? detail.message : strings.knowledge.requestFailed
      return new ApiRequestError(message, code, response.status)
    }
  } catch {
    // The fallback below keeps server or network errors in Persian.
  }
  return new ApiRequestError(strings.knowledge.requestFailed, 'request_failed', response.status)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
