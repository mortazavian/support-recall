export type HealthStatus = {
  status: string
  storage: string
  service: string
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
