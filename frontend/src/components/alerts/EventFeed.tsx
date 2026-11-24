import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  fetchAlerts,
  fetchDevices,
  fetchLocationConfig,
  fetchLocations,
  type AlertDto,
  type AlertSeverity,
  type AlertStatusFilter,
  type LocationConfigDto,
} from '../../services/api'
import { subscribeRealtime } from '../../services/realtime'

type Status = 'loading' | 'ready' | 'error'

/** Poll every 5 seconds. Phase 12 replaces this with the WebSocket. */
const POLL_MS = 5000
const LIMIT = 50

const SEVERITY_TONE: Record<AlertSeverity, string> = {
  info: 'bg-glass-100 text-ink-soft',
  warning: 'bg-sun-50 text-sun-500',
  critical: 'bg-clay-50 text-clay-500',
}

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}

function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${SEVERITY_TONE[severity]}`}>
      {severity}
    </span>
  )
}

/**
 * Phase 11 event feed. Alerts come from the database, so they survive a refresh.
 * The backend decides what is an alert; this only shows them.
 */
export default function EventFeed() {
  const [alerts, setAlerts] = useState<AlertDto[]>([])
  const [configs, setConfigs] = useState<LocationConfigDto[]>([])
  const [deviceNames, setDeviceNames] = useState<Map<string, string>>(new Map())
  const [locationId, setLocationId] = useState('')
  const [zoneId, setZoneId] = useState('')
  const [statusFilter, setStatusFilter] = useState<AlertStatusFilter>('active')
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  // Locations, zones and device names, for the filters and labels.
  const loadLookups = useCallback(async (signal?: AbortSignal) => {
    try {
      const [locations, devices] = await Promise.all([
        fetchLocations(signal),
        fetchDevices({}, signal),
      ])
      const loaded = await Promise.all(
        locations.map((location) => fetchLocationConfig(location.id, signal)),
      )
      setConfigs(loaded)
      setDeviceNames(
        new Map(devices.map((device) => [device.id, device.display_name || device.device_type])),
      )
    } catch (caught) {
      if (signal?.aborted) return
      setError(errorText(caught, 'Could not load locations for the filters.'))
    }
  }, [])

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const rows = await fetchAlerts(
          {
            status: statusFilter,
            locationId: locationId || undefined,
            zoneId: zoneId || undefined,
            limit: LIMIT,
          },
          signal,
        )
        setAlerts(rows)
        setStatus('ready')
        setError(null)
        setUpdatedAt(new Date())
      } catch (caught) {
        if (signal?.aborted) return
        setStatus('error')
        setError(errorText(caught, 'Could not load alerts.'))
      }
    },
    [statusFilter, locationId, zoneId],
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadLookups(controller.signal)
    return () => controller.abort()
  }, [loadLookups])

  // Load now, then every 5 seconds. Changing a filter restarts the timer.
  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    const timer = window.setInterval(() => void load(controller.signal), POLL_MS)
    return () => {
      window.clearInterval(timer)
      controller.abort()
    }
  }, [load])

  // Does nothing until Phase 12. Then a new alert reloads the feed at once.
  useEffect(
    () =>
      subscribeRealtime((event) => {
        if (event.type === 'alert.created') void load()
      }),
    [load],
  )

  const zones = useMemo(
    () => configs.find((config) => config.location.id === locationId)?.zones ?? [],
    [configs, locationId],
  )

  const placeNames = useMemo(() => {
    const names = new Map<string, string>()
    for (const config of configs) {
      for (const zone of config.zones) {
        names.set(zone.id, `${config.location.name} · ${zone.name}`)
      }
    }
    return names
  }, [configs])

  function place(alert: AlertDto): string {
    if (alert.zone_id) return placeNames.get(alert.zone_id) ?? 'Unknown zone'
    return 'Unassigned'
  }

  function device(alert: AlertDto): string {
    if (!alert.device_id) return 'Deleted device'
    return deviceNames.get(alert.device_id) ?? alert.device_id.slice(0, 8)
  }

  const selectClass = 'rounded-md border border-line bg-white px-2 py-1.5 text-sm'

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-ink-soft">
          Location
          <select
            className={selectClass}
            value={locationId}
            onChange={(event) => {
              setLocationId(event.target.value)
              setZoneId('') // a zone belongs to one location
            }}
          >
            <option value="">All locations</option>
            {configs.map((config) => (
              <option key={config.location.id} value={config.location.id}>
                {config.location.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-ink-soft">
          Zone
          <select
            className={selectClass}
            value={zoneId}
            disabled={!locationId}
            onChange={(event) => setZoneId(event.target.value)}
          >
            <option value="">{locationId ? 'All zones' : 'Pick a location first'}</option>
            {zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-ink-soft">
          Status
          <select
            className={selectClass}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as AlertStatusFilter)}
          >
            <option value="active">Active</option>
            <option value="resolved">Resolved</option>
            <option value="all">All</option>
          </select>
        </label>

        <button
          type="button"
          onClick={() => {
            void loadLookups()
            void load()
          }}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-soft"
        >
          Refresh
        </button>

        <span className="ml-auto text-xs text-ink-soft">
          {updatedAt ? `Updated ${updatedAt.toLocaleTimeString()} · every 5 s` : 'Polling every 5 s'}
        </span>
      </div>

      {error && (
        <p role="alert" className="text-sm text-clay-500">
          {error}
        </p>
      )}

      {status === 'loading' ? (
        <p className="text-sm text-ink-soft">Loading events…</p>
      ) : alerts.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-ink-soft">
          No alerts{locationId ? ' for this filter' : ''}. A moisture reading below its zone's low
          threshold, a failed command or an actuator entering error will show up here.
        </p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line">
          {alerts.map((alert) => (
            <li key={alert.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2">
              <SeverityBadge severity={alert.severity} />
              <span className="text-sm text-ink">{alert.message}</span>
              <span className="font-mono text-xs text-ink-soft">{alert.event_type}</span>
              <span className="text-xs text-ink-soft">
                {device(alert)} · {place(alert)}
              </span>
              <span className="ml-auto whitespace-nowrap text-xs text-ink-soft">
                {new Date(alert.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}