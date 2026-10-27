import { useCallback, useEffect, useState, type ReactNode } from 'react'

import {
  fetchLocations,
  fetchOverview,
  type LocationOverviewDto,
  type LocationSummaryDto,
  type OverviewDeviceDto,
  type OverviewReadingDto,
  type OverviewZoneDto,
} from '../../services/api'

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}

function SummaryCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line p-4">
      <p className="text-xs uppercase tracking-wide text-ink-soft">{label}</p>
      <div className="mt-1 text-sm text-ink">{children}</div>
    </div>
  )
}

function ActionBadge({ action }: { action: string }) {
  const tone = action === 'irrigate' ? 'bg-sun-50 text-sun-500' : 'bg-moss-50 text-moss-700'
  return <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>{action}</span>
}

function DeviceLine({
  device,
  reading,
}: {
  device: OverviewDeviceDto
  reading?: OverviewReadingDto
}) {
  return (
    <li className="space-y-0.5 py-2">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-sm text-ink">{device.display_name ?? device.device_type}</span>
        <span className="text-xs text-ink-soft">
          {device.role} · {device.device_type}
        </span>
      </div>
      {reading ? (
        <p className="text-xs text-ink-soft">
          {reading.value.toFixed(2)} {reading.unit}
          {' · '}tracking {reading.tracking_enabled ? 'on' : 'off'}
          {' · '}every {reading.sampling_interval_seconds}s
          {' · '}
          {new Date(reading.recorded_at).toLocaleTimeString()}
        </p>
      ) : (
        <p className="text-xs italic text-ink-soft">No reading yet</p>
      )}
    </li>
  )
}

function ZoneCard({ zone }: { zone: OverviewZoneDto }) {
  const readings = new Map(zone.latest_readings.map((reading) => [reading.device_id, reading]))

  return (
    <div className="rounded-lg border border-line p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-display text-base font-semibold">{zone.name}</h3>
        <span className="text-xs text-ink-soft">
          moisture {zone.moisture_threshold_low.toFixed(2)}–
          {zone.moisture_threshold_high.toFixed(2)}
        </span>
      </div>
      {zone.devices.length === 0 ? (
        <p className="mt-2 text-sm text-ink-soft">No devices assigned to this zone.</p>
      ) : (
        <ul className="mt-1 divide-y divide-line">
          {zone.devices.map((device) => (
            <DeviceLine key={device.id} device={device} reading={readings.get(device.id)} />
          ))}
        </ul>
      )}
    </div>
  )
}

export default function OverviewPanel({ configVersion = 0 }: { configVersion?: number }) {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([])
  const [locationId, setLocationId] = useState('')
  const [overview, setOverview] = useState<LocationOverviewDto | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    fetchLocations(controller.signal)
      .then((sites) => {
        setLocations(sites)
        setLocationId((current) =>
          sites.some((site) => site.id === current) ? current : (sites[0]?.id ?? ''),
        )
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorText(caught, 'Could not load locations.'))
      })

    return () => controller.abort()
  }, [configVersion])

  const load = useCallback(async (id: string, signal?: AbortSignal) => {
    setLoading(true)
    try {
      setOverview(await fetchOverview(id, signal))
      setError(null)
    } catch (caught) {
      if (!signal?.aborted) setError(errorText(caught, 'Could not load the overview.'))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!locationId) return
    const controller = new AbortController()
    void load(locationId, controller.signal)
    return () => controller.abort()
  }, [locationId, load])

  if (locations.length === 0 && !error) {
    return (
      <p className="text-sm text-ink-soft">
        No locations yet. Create one in Configuration to see its overview.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="overview-location" className="text-sm text-ink-soft">
          Location
        </label>
        <select
          id="overview-location"
          value={locationId}
          onChange={(event) => setLocationId(event.target.value)}
          className="rounded-md border border-line bg-white px-2 py-1.5 text-sm"
        >
          {locations.map((site) => (
            <option key={site.id} value={site.id}>
              {site.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => void load(locationId)}
          disabled={!locationId || loading}
          className="rounded-md bg-moss-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {overview && locationId && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard label="Assigned sensors">
              <span className="font-display text-2xl">{overview.device_counts.sensor}</span>
            </SummaryCard>
            <SummaryCard label="Assigned actuators">
              <span className="font-display text-2xl">{overview.device_counts.actuator}</span>
            </SummaryCard>
            <SummaryCard label="Strategy">
              {overview.strategy_key ?? (
                <span className="text-ink-soft">No strategy saved yet</span>
              )}
            </SummaryCard>
            <SummaryCard label="Recommendation">
              {overview.last_recommendation ? (
                <div className="space-y-1">
                  <ActionBadge action={overview.last_recommendation.action} />
                  <p className="text-ink-soft">{overview.last_recommendation.reason}</p>
                </div>
              ) : (
                <span className="text-ink-soft">Save a strategy in Automation to get one</span>
              )}
            </SummaryCard>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {overview.zones.map((zone) => (
              <ZoneCard key={zone.id} zone={zone} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}