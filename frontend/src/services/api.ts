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

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers:
      body === undefined
        ? { Accept: 'application/json' }
        : { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    const detail = await errorDetail(response, `Request failed with status ${response.status}`)
    throw new ApiError(detail, response.status)
  }

  // 204 No Content has no body to parse.
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
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
  /** Phase 5 columns. The copy inside default_config is history, not the truth. */
  sampling_interval_seconds: number
  tracking_enabled: boolean
}

/** Creator keys the backend accepts. */
export type SensorType = 'moisture' | 'light'

export function fetchSensors(signal?: AbortSignal): Promise<SensorDto[]> {
  return request<SensorDto[]>('/api/sensors', signal)
}

export function createSensor(type: SensorType, displayName?: string): Promise<SensorDto> {
  return send<SensorDto>('POST', '/api/sensors', { type, display_name: displayName ?? null })
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
  /** Where the device sits. Both null when it is unassigned. */
  zone_id: string | null
  location_id: string | null
  /** Phase 5 sampling columns. */
  sampling_interval_seconds: number
  tracking_enabled: boolean
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
export function provisionDeviceFamily(family: DeviceFamily): Promise<DeviceDto[]> {
  return send<DeviceDto[]>('POST', `/api/devices/provision?family=${encodeURIComponent(family)}`)
}

/** Place a device in a zone, or pass null to clear its placement. */
export function assignDeviceZone(deviceId: string, zoneId: string | null): Promise<DeviceDto> {
  return send<DeviceDto>('PATCH', `/api/devices/${deviceId}/zone`, { zone_id: zoneId })
}

// ---------------------------------------------------------------------------
// Locations and zones (Phase 4 - Builder)
// ---------------------------------------------------------------------------

export interface LocationSummaryDto {
  id: string
  name: string
}

/** A saved zone. Note location_id, never greenhouse_id. */
export interface ZoneDto {
  id: string
  location_id: string
  name: string
  moisture_threshold_low: number
  moisture_threshold_high: number
  schedule: Record<string, unknown>
}

export interface LocationConfigDto {
  location: LocationSummaryDto
  zones: ZoneDto[]
}

/** One zone as the client sends it, on create or on add/edit. */
export interface ZoneInput {
  name: string
  moisture_threshold_low: number
  moisture_threshold_high: number
  schedule?: Record<string, unknown>
}

export function fetchLocations(signal?: AbortSignal): Promise<LocationSummaryDto[]> {
  return request<LocationSummaryDto[]>('/api/locations', signal)
}

export function fetchLocationConfig(
  locationId: string,
  signal?: AbortSignal,
): Promise<LocationConfigDto> {
  return request<LocationConfigDto>(`/api/locations/${locationId}/config`, signal)
}

export function createLocationConfig(
  locationName: string,
  zones: ZoneInput[],
): Promise<LocationConfigDto> {
  return send<LocationConfigDto>('POST', '/api/locations/config', {
    location_name: locationName,
    zones,
  })
}

export function deleteLocation(locationId: string): Promise<void> {
  return send<void>('DELETE', `/api/locations/${locationId}`)
}

export function addZone(locationId: string, zone: ZoneInput): Promise<ZoneDto> {
  return send<ZoneDto>('POST', `/api/locations/${locationId}/zones`, zone)
}

export function updateZone(
  locationId: string,
  zoneId: string,
  zone: ZoneInput,
): Promise<ZoneDto> {
  return send<ZoneDto>('PATCH', `/api/locations/${locationId}/zones/${zoneId}`, zone)
}

export function deleteZone(locationId: string, zoneId: string): Promise<void> {
  return send<void>('DELETE', `/api/locations/${locationId}/zones/${zoneId}`)
}

export function fetchZoneDevices(
  locationId: string,
  zoneId: string,
  signal?: AbortSignal,
): Promise<DeviceDto[]> {
  return request<DeviceDto[]>(`/api/locations/${locationId}/zones/${zoneId}/devices`, signal)
}

// ---------------------------------------------------------------------------
// Readings (Phase 5 — Adapter)
// --------------------------------------------
/** Where a reading came from. The adapter's signature, shown as a badge. */
export type ReadingSource = 'simulation' | 'vendor' | 'mqtt'

/** Matches ReadingDto on the backend, field for field. */
export interface ReadingDto {
  device_id: string
  value: number
  unit: string
  source: string
  /** ISO-8601 with an offset, e.g. 2026-08-28T09:00:00+00:00 */
  recorded_at: string
}

/**
 * Ask a device's adapter for a value now, and store it.
 *
 * A device on the mqtt protocol answers 400: it publishes for itself rather
 * than responding to a request. Cards hide the button for those.
 */
export function takeReading(deviceId: string): Promise<ReadingDto> {
  return send<ReadingDto>('POST', `/api/sensors/${deviceId}/read`)
}

/** Recent readings for a device, newest first. Pass limit 1 for just the latest. */
export function fetchReadings(
  deviceId: string,
  limit = 20,
  signal?: AbortSignal,
): Promise<ReadingDto[]> {
  return request<ReadingDto[]>(`/api/sensors/${deviceId}/readings?limit=${limit}`, signal)
}

/** Change how often the sampler records a device, or stop it entirely. */
export function updateSampling(
  deviceId: string,
  samplingIntervalSeconds: number,
  trackingEnabled: boolean,
): Promise<DeviceDto> {
  return send<DeviceDto>('PATCH', `/api/devices/${deviceId}/sampling`, {
    sampling_interval_seconds: samplingIntervalSeconds,
    tracking_enabled: trackingEnabled,
  })
}