import { useEffect, useState } from 'react'

import { getHealth, type HealthResponse } from '../services/api'

const POLL_INTERVAL_MS = 15_000

type Probe =
  | { phase: 'checking' }
  | { phase: 'answered'; health: HealthResponse }
  | { phase: 'unreachable' }


export default function HealthStatus() {
  const [probe, setProbe] = useState<Probe>({ phase: 'checking' })

  useEffect(() => {
    const controller = new AbortController()

    async function check() {
      try {
        const health = await getHealth(controller.signal)
        setProbe({ phase: 'answered', health })
      } catch {
        if (!controller.signal.aborted) {
          setProbe({ phase: 'unreachable' })
        }
      }
    }

    void check()
    const timer = window.setInterval(() => void check(), POLL_INTERVAL_MS)

    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [])

  const apiUp = probe.phase === 'answered'
  const dbUp = probe.phase === 'answered' && probe.health.db === 'ok'
  const checking = probe.phase === 'checking'

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 rounded-full border border-line bg-white px-3 py-1.5 text-sm"
    >
      <span className="sr-only">{describe(probe)}</span>
      <Indicator label="API" up={apiUp} checking={checking} />
      <span aria-hidden className="h-4 w-px bg-line" />
      <Indicator label="Database" up={dbUp} checking={checking} />
    </div>
  )
}

function Indicator({
  label,
  up,
  checking,
}: {
  label: string
  up: boolean
  checking: boolean
}) {
  const dot = checking
    ? 'bg-moss-300 animate-pulse motion-reduce:animate-none'
    : up
      ? 'bg-moss-500'
      : 'bg-clay-500'

  return (
    <span aria-hidden className="flex items-center gap-1.5">
      <span className={`size-2 rounded-full ${dot}`} />
      <span className={checking || up ? 'text-ink-soft' : 'text-clay-500'}>{label}</span>
    </span>
  )
}

function describe(probe: Probe): string {
  if (probe.phase === 'checking') return 'Checking service health.'
  if (probe.phase === 'unreachable') return 'API unreachable. Start the backend on port 8000.'
  return probe.health.db === 'ok'
    ? 'API responding, database connected.'
    : 'API responding, database unreachable. Start the Postgres container.'
}
