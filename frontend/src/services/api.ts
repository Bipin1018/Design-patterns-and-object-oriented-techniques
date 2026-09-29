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

/** The API sends { "detail": "..." } on a 400. Show that rather than a generic message. */
async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    if (typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // No JSON body; fall through.
  }
  return fallback
}

/** Ask the API whether it is up and whether it can reach PostgreSQL. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', signal)
}

// ---------------------------------------------------------------------------
// Sensors (Phase 2 — Factory Method)
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

export async function createSensor(type: SensorType, displayName?: string): Promise<SensorDto> {
  const response = await fetch(`${API_BASE_URL}/api/sensors`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ type, display_name: displayName ?? null }),
  })

  if (!response.ok) {
    const detail = await errorDetail(response, `Request failed with status ${response.status}`)
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as SensorDto
}

// ---------------------------------------------------------------------------
// Devices (Phase 3 — Abstract Factory)
// ---------------------------------------------------------------------------

/** Families the backend can provision. */
export type DeviceFamily = 'simulation' | 'edge'

/** A device is either something that reads or something that acts. */
export type DeviceRole = 'sensor' | 'actuator'

/** Matches DeviceDto on the backend, field for field. */
export interface DeviceDto {
  id: string
  device_type: string
  role: DeviceRole
  device_family: string
  display_name: string
  default_config: Record<string, unknown>
}

export function fetchDevices(
  filters: { family?: DeviceFamily; role?: DeviceRole } = {},
  signal?: AbortSignal,
): Promise<DeviceDto[]> {
  const params = new URLSearchParams()
  if (filters.family) params.set('family', filters.family)
  if (filters.role) params.set('role', filters.role)

  const query = params.toString()
  return request<DeviceDto[]>(`/api/devices${query ? `?${query}` : ''}`, signal)
}

/** Create a whole matching kit for one family. Returns the four new devices. */
export async function provisionDeviceFamily(family: DeviceFamily): Promise<DeviceDto[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/devices/provision?family=${encodeURIComponent(family)}`,
    { method: 'POST', headers: { Accept: 'application/json' } },
  )

  if (!response.ok) {
    const detail = await errorDetail(response, `Request failed with status ${response.status}`)
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as DeviceDto[]
}