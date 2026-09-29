import { useCallback, useEffect, useState } from 'react'

import {
  assignDeviceZone,
  fetchDevices,
  fetchLocationConfig,
  fetchLocations,
  provisionDeviceFamily,
  type DeviceDto,
  type DeviceFamily,
  type ZoneDto,
} from '../../services/api'
import DeviceFamilySwitcher from './DeviceFamilySwitcher'

type Status = 'loading' | 'ready' | 'error'

/** One location with its zones, for the picker's grouped options. */
type ZoneGroup = {
  locationId: string
  locationName: string
  zones: ZoneDto[]
}

export default function DeviceList({ configVersion = 0 }: { configVersion?: number }) {
  const [family, setFamily] = useState<DeviceFamily>('simulation')
  const [devices, setDevices] = useState<DeviceDto[]>([])
  const [groups, setGroups] = useState<ZoneGroup[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)
  const [provisioning, setProvisioning] = useState(false)

  // Every list request carries the family, so the two kits never mix.
  const load = useCallback(async (selected: DeviceFamily, signal?: AbortSignal) => {
    setStatus('loading')
    try {
      setDevices(await fetchDevices({ family: selected }, signal))
      setStatus('ready')
      setError(null)
    } catch (caught) {
      if (signal?.aborted) return
      setStatus('error')
      setError(caught instanceof Error ? caught.message : 'Could not load devices.')
    }
  }, [])

  /** Every saved location with its zones, so the picker can offer them all. */
  const loadZoneOptions = useCallback(async (signal?: AbortSignal) => {
    try {
      const locations = await fetchLocations(signal)
      const loaded = await Promise.all(
        locations.map(async (location) => {
          const config = await fetchLocationConfig(location.id, signal)
          return { locationId: location.id, locationName: location.name, zones: config.zones }
        }),
      )
      setGroups(loaded)
    } catch {
      // A missing config list should not break the device list itself.
      setGroups([])
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(family, controller.signal)
    return () => controller.abort()
  }, [family, load])

  // configVersion changes whenever the wizard edits a location, so the picker
  // and the placements stay in step with it.
  useEffect(() => {
    const controller = new AbortController()
    void loadZoneOptions(controller.signal)
    if (configVersion > 0) void load(family, controller.signal)
    return () => controller.abort()
  }, [configVersion, loadZoneOptions, load, family])

  async function provision() {
    setProvisioning(true)
    setError(null)
    try {
      await provisionDeviceFamily(family)
      await load(family)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not provision the kit.')
    } finally {
      setProvisioning(false)
    }
  }

  async function changeZone(device: DeviceDto, zoneId: string | null) {
    setError(null)
    try {
      const updated = await assignDeviceZone(device.id, zoneId)
      setDevices((current) => current.map((d) => (d.id === updated.id ? updated : d)))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not change the zone.')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <DeviceFamilySwitcher value={family} onChange={setFamily} disabled={provisioning} />
        <button
          type="button"
          onClick={() => void provision()}
          disabled={provisioning}
          className="rounded-lg bg-moss-500 px-3 py-1.5 text-sm text-white transition-colors hover:bg-moss-700 disabled:opacity-50"
        >
          {provisioning ? 'Provisioning…' : 'Provision this kit'}
        </button>
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-clay-50 px-3 py-2 text-sm text-clay-500">
          {error}
        </p>
      )}

      {status === 'loading' && <p className="text-sm text-ink-soft">Loading devices…</p>}

      {status === 'ready' && devices.length === 0 && (
        <p className="text-sm text-ink-soft">
          No devices in this family yet. Provision a kit to create two sensors and two actuators.
        </p>
      )}

      {devices.length > 0 && (
        <ul className="divide-y divide-line">
          {devices.map((device) => (
            <li key={device.id} className="space-y-1 py-3">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-medium">{device.display_name}</span>
                <RoleBadge role={device.role} />
                <span className="rounded bg-glass-100 px-1.5 py-0.5 text-xs text-ink-soft">
                  {device.device_family}
                </span>
                <span className="text-xs text-ink-soft">
                  {describeConfig(device.default_config)}
                </span>
              </div>
              <ZonePicker
                device={device}
                groups={groups}
                onChange={(zoneId) => void changeZone(device, zoneId)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ZonePicker({
  device,
  groups,
  onChange,
}: {
  device: DeviceDto
  groups: ZoneGroup[]
  onChange: (zoneId: string | null) => void
}) {
  if (groups.length === 0) {
    return (
      <p className="text-xs text-ink-soft">
        No locations yet. Create one under Configuration to place this device.
      </p>
    )
  }

  return (
    <label className="flex flex-wrap items-center gap-2 text-xs text-ink-soft">
      Zone
      <select
        value={device.zone_id ?? ''}
        onChange={(event) => onChange(event.target.value || null)}
        className="rounded-md border border-line bg-white px-2 py-1 text-xs"
      >
        <option value="">Unassigned</option>
        {groups.map((group) => (
          <optgroup key={group.locationId} label={group.locationName}>
            {group.zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {group.locationName} — {zone.name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  )
}

function RoleBadge({ role }: { role: DeviceDto['role'] }) {
  const tone = role === 'sensor' ? 'bg-moss-50 text-moss-700' : 'bg-sun-50 text-sun-500'
  return <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>{role}</span>
}

function describeConfig(config: Record<string, unknown>): string {
  return Object.entries(config)
    .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${String(value)}`)
    .join(' · ')
}