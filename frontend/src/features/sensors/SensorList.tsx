import { useCallback, useEffect, useState } from 'react'

import { createSensor, fetchSensors, type SensorDto, type SensorType } from '../../services/api'

type Status = 'loading' | 'ready' | 'error'

const ADDABLE: { type: SensorType; label: string }[] = [
  { type: 'moisture', label: 'Add moisture sensor' },
  { type: 'light', label: 'Add light sensor' },
]

export default function SensorList() {
  const [sensors, setSensors] = useState<SensorDto[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<SensorType | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setSensors(await fetchSensors(signal))
      setStatus('ready')
      setError(null)
    } catch (caught) {
      if (signal?.aborted) return
      setStatus('error')
      setError(caught instanceof Error ? caught.message : 'Could not load sensors.')
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function add(type: SensorType) {
    setPending(type)
    setError(null)
    try {
      const created = await createSensor(type)
      setSensors((current) => [created, ...current])
      setStatus('ready')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not add the sensor.')
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {ADDABLE.map(({ type, label }) => (
          <button
            key={type}
            type="button"
            onClick={() => void add(type)}
            disabled={pending !== null}
            className="rounded-lg bg-moss-500 px-3 py-1.5 text-sm text-white transition-colors hover:bg-moss-700 disabled:opacity-50"
          >
            {pending === type ? 'Adding…' : label}
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-clay-50 px-3 py-2 text-sm text-clay-500">
          {error}
        </p>
      )}

      {status === 'loading' && <p className="text-sm text-ink-soft">Loading sensors…</p>}

      {status === 'ready' && sensors.length === 0 && (
        <p className="text-sm text-ink-soft">
          No sensors yet. Add one above and it will be saved to the database.
        </p>
      )}

      {sensors.length > 0 && (
        <ul className="divide-y divide-line">
          {sensors.map((sensor) => (
            <li key={sensor.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3">
              <span className="font-medium">{sensor.display_name}</span>
              <span className="rounded bg-glass-100 px-1.5 py-0.5 text-xs text-ink-soft">
                {sensor.device_type}
              </span>
              <span className="text-xs text-ink-soft">{describeConfig(sensor.default_config)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function describeConfig(config: Record<string, unknown>): string {
  return Object.entries(config)
    .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${String(value)}`)
    .join(' · ')
}
