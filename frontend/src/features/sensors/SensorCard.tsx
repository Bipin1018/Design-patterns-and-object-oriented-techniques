import { useCallback, useEffect, useState } from 'react'

import {
  fetchReadings,
  takeReading,
  updateSampling,
  type ReadingDto,
  type SensorDto,
} from '../../services/api'

/**
 * Temporary until Phase 12.
 *
 * Every card asks the API for its latest row every few seconds, which is how
 * sampler readings appear without anyone pressing a button. Phase 12 replaces
 * this with one WebSocket that pushes reading.created to the whole dashboard,
 * so the polling goes away entirely.
 */
const POLL_INTERVAL_MS = 5_000

const MIN_INTERVAL_SECONDS = 5

type Props = {
  sensor: SensorDto
  onSamplingChange: () => void
}

export default function SensorCard({ sensor, onSamplingChange }: Props) {
  const [latest, setLatest] = useState<ReadingDto | null>(null)
  const [loading, setLoading] = useState(true)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Draft value for the interval box, so typing does not fire a PATCH per key.
  // Named intervalDraft, not interval: the browser already has a global by
  // that name, and shadowing it inside a module is asking for trouble.
  const [intervalDraft, setIntervalDraft] = useState(String(sensor.sampling_interval_seconds))
  const [saving, setSaving] = useState(false)

  const protocol = readProtocol(sensor)
  // An mqtt device publishes for itself, so asking it for a value is a 400.
  // Hiding the button is kinder than letting someone find that out.
  const canReadOnDemand = protocol !== 'mqtt'

  const loadLatest = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const rows = await fetchReadings(sensor.id, 1, signal)
        setLatest(rows[0] ?? null)
        setError(null)
      } catch (caught) {
        if (signal?.aborted) return
        setError(caught instanceof Error ? caught.message : 'Could not load the reading.')
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [sensor.id],
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadLatest(controller.signal)

    const timer = window.setInterval(() => void loadLatest(controller.signal), POLL_INTERVAL_MS)

    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [loadLatest])

  async function readNow() {
    setReading(true)
    setError(null)
    try {
      // Show what the API returned. The row is in the database either way, so
      // a refresh finds the same number.
      setLatest(await takeReading(sensor.id))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not take a reading.')
    } finally {
      setReading(false)
    }
  }

  async function saveSampling(seconds: number, enabled: boolean) {
    setSaving(true)
    setError(null)
    try {
      await updateSampling(sensor.id, seconds, enabled)
      onSamplingChange()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the settings.')
      // Put the input back to what the server still holds.
      setIntervalDraft(String(sensor.sampling_interval_seconds))
    } finally {
      setSaving(false)
    }
  }

  function commitInterval() {
    const seconds = Number(intervalDraft)
    if (!Number.isFinite(seconds) || seconds === sensor.sampling_interval_seconds) {
      setIntervalDraft(String(sensor.sampling_interval_seconds))
      return
    }
    void saveSampling(Math.trunc(seconds), sensor.tracking_enabled)
  }

  return (
    <li className="space-y-3 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-medium">{sensor.display_name}</span>
        <span className="rounded bg-glass-100 px-1.5 py-0.5 text-xs text-ink-soft">
          {sensor.device_type}
        </span>
        <span className="rounded bg-glass-100 px-1.5 py-0.5 text-xs text-ink-soft">
          {protocol}
        </span>
        {!sensor.tracking_enabled && (
          <span className="rounded bg-sun-50 px-1.5 py-0.5 text-xs text-sun-500">
            tracking off
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Latest loading={loading} reading={latest} />

        {canReadOnDemand ? (
          <button
            type="button"
            onClick={() => void readNow()}
            disabled={reading}
            className="rounded-lg bg-moss-500 px-3 py-1.5 text-sm text-white transition-colors hover:bg-moss-700 disabled:opacity-50"
          >
            {reading ? 'Reading…' : 'Read now'}
          </button>
        ) : (
          <span className="text-xs text-ink-soft">
            Reports over MQTT, so it cannot be read on demand.
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-soft">
        <label className="flex items-center gap-2">
          Sample every
          <input
            type="number"
            min={MIN_INTERVAL_SECONDS}
            value={intervalDraft}
            disabled={saving}
            onChange={(event) => setIntervalDraft(event.target.value)}
            onBlur={commitInterval}
            className="w-20 rounded-md border border-line bg-white px-2 py-1 text-xs disabled:opacity-50"
          />
          seconds
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={sensor.tracking_enabled}
            disabled={saving}
            onChange={(event) =>
              void saveSampling(sensor.sampling_interval_seconds, event.target.checked)
            }
            className="size-3.5 accent-moss-500"
          />
          Tracking
        </label>

        {saving && <span>Saving…</span>}
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-clay-50 px-3 py-2 text-sm text-clay-500">
          {error}
        </p>
      )}
    </li>
  )
}

function Latest({ loading, reading }: { loading: boolean; reading: ReadingDto | null }) {
  if (loading) {
    return <span className="text-sm text-ink-soft">Loading…</span>
  }

  if (reading === null) {
    return <span className="text-sm text-ink-soft">No readings yet.</span>
  }

  return (
    <span className="flex items-baseline gap-2">
      <span className="font-display text-2xl font-semibold text-moss-700">{reading.value}</span>
      <span className="text-sm text-ink-soft">{reading.unit}</span>
      <SourceBadge source={reading.source} />
      <span className="text-xs text-ink-soft">{timeAgo(reading.recorded_at)}</span>
    </span>
  )
}

/** Which adapter produced this value. Three sources, three tones. */
function SourceBadge({ source }: { source: string }) {
  const tone =
    source === 'simulation'
      ? 'bg-moss-50 text-moss-700'
      : source === 'mqtt'
        ? 'bg-sun-50 text-sun-500'
        : 'bg-glass-100 text-ink-soft'

  return <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>{source}</span>
}

/** The protocol lives in default_config, written by the creator or the family. */
function readProtocol(sensor: SensorDto): string {
  const protocol = sensor.default_config.protocol
  return typeof protocol === 'string' && protocol ? protocol : 'simulation'
}

function timeAgo(isoTimestamp: string): string {
  const seconds = Math.round((Date.now() - new Date(isoTimestamp).getTime()) / 1000)

  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}