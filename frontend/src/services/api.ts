/**
 * The only place in the app that talks to the backend.
 * Pages and components import from here instead of calling fetch directly.
 */

export interface HealthResponse {
  status: string
  db: 'ok' | 'fail'
}

/** Backend origin. Set VITE_API_BASE_URL in .env.local to point somewhere else. */
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    signal,
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed with status ${response.status}`, response.status)
  }

  return (await response.json()) as T
}

/** Ask the API whether it is up and whether it can reach PostgreSQL. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', signal)
}

// ---------------------------------------------------------------------------
// Sensors
// ---------------------------------------------------------------------------

/** Shape returned by GET and POST /api/sensors. Field names match the backend. */
export interface SensorDto {
  id: string
  device_type: string
  display_name: string
  default_config: Record<string, unknown>
}

/** Creator keys the backend accepts. */
export type SensorType = 'moisture' | 'light'

export function fetchSensors(signal?: AbortSignal): Promise<SensorDto[]> {
  return request<SensorDto[]>('/api/sensors', signal)
}

export async function createSensor(
  type: SensorType,
  displayName?: string,
): Promise<SensorDto> {
  const response = await fetch(`${API_BASE_URL}/api/sensors`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ type, display_name: displayName ?? null }),
  })

  if (!response.ok) {
    // The API sends { "detail": "..." } on a 400, which is worth showing.
    let detail = `Request failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // Response had no JSON body; keep the generic message.
    }
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as SensorDto
}