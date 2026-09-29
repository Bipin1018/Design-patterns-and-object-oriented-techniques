import { useCallback, useEffect, useState } from 'react'

import {
  fetchDevices,
  provisionDeviceFamily,
  type DeviceDto,
  type DeviceFamily,
} from '../../services/api'
import DeviceFamilySwitcher from './DeviceFamilySwitcher'

type Status = 'loading' | 'ready' | 'error'

export default function DeviceList() {
  const [family, setFamily] = useState<DeviceFamily>('simulation')
  const [devices, setDevices] = useState<DeviceDto[]>([])
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

  useEffect(() => {
    const controller = new AbortController()
    void load(family, controller.signal)
    return () => controller.abort()
  }, [family, load])

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
            <li key={device.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3">
              <span className="font-medium">{device.display_name}</span>
              <RoleBadge role={device.role} />
              <span className="rounded bg-glass-100 px-1.5 py-0.5 text-xs text-ink-soft">
                {device.device_family}
              </span>
              <span className="text-xs text-ink-soft">{describeConfig(device.default_config)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
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