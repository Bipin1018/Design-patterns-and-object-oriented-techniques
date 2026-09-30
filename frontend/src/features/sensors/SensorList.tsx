import { useCallback, useEffect, useState } from 'react'

import { createSensor, fetchSensors, type SensorDto, type SensorType } from '../../services/api'
import SensorCard from './SensorCard'

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
            <SensorCard
              key={sensor.id}
              sensor={sensor}
              // A card only knows what it was given, so after it saves an
              // interval or a tracking flag the list re-reads the sensors and
              // hands the card its new values.
              onSamplingChange={() => void load()}
            />
          ))}
        </ul>
      )}
    </div>
  )
}