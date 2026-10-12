import { useCallback, useEffect, useState } from 'react'

import {
  evaluateAutomation,
  fetchAutomationRule,
  fetchLocations,
  fetchStrategies,
  saveAutomationRule,
  type EvaluationDto,
  type LocationSummaryDto,
  type StrategyOptionDto,
  type ZoneRecommendationDto,
} from '../../services/api'

function ActionBadge({ action }: { action: string }) {
  const tone = action === 'irrigate' ? 'bg-sun-50 text-sun-500' : 'bg-moss-50 text-moss-700'

  return <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>{action}</span>
}

function ZoneResult({ zone }: { zone: ZoneRecommendationDto }) {
  const reading = zone.moisture === null ? 'no reading' : `moisture ${zone.moisture.toFixed(2)}`
  const band = `band ${zone.moisture_low.toFixed(2)} to ${zone.moisture_high.toFixed(2)}`
  const urgency = zone.score !== null && zone.score > 0 ? ` · urgency ${zone.score.toFixed(2)}` : ''

  return (
    <li className="space-y-1 py-3">
      <div className="flex items-center gap-2">
        <span className="text-sm">{zone.zone_name}</span>
        <ActionBadge action={zone.action} />
      </div>
      <p className="text-sm text-ink-soft">{zone.reason}</p>
      <p className="text-xs text-ink-soft">
        {reading} · {band}
        {urgency}
      </p>
    </li>
  )
}

export function StrategyPanel({ configVersion = 0 }: { configVersion?: number }) {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([])
  const [locationId, setLocationId] = useState('')
  const [strategies, setStrategies] = useState<StrategyOptionDto[]>([])
  const [selectedKey, setSelectedKey] = useState('')
  const [savedKey, setSavedKey] = useState('')
  const [persisted, setPersisted] = useState(false)
  const [result, setResult] = useState<EvaluationDto | null>(null)
  const [pending, setPending] = useState<'save' | 'evaluate' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const [sites, options] = await Promise.all([
          fetchLocations(controller.signal),
          fetchStrategies(controller.signal),
        ])
        setLocations(sites)
        setStrategies(options)
        if (sites.length > 0) setLocationId((current) => current || sites[0].id)
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : 'Could not load automation.')
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [configVersion])

  const loadRule = useCallback(async (id: string, signal?: AbortSignal) => {
    try {
      const rule = await fetchAutomationRule(id, signal)
      setSelectedKey(rule.strategy_key)
      setSavedKey(rule.strategy_key)
      setPersisted(rule.persisted)
      setError(null)
    } catch (caught) {
      if (!signal?.aborted) {
        setError(caught instanceof Error ? caught.message : 'Could not load the saved strategy.')
      }
    }
  }, [])

  useEffect(() => {
    if (!locationId) return

    const controller = new AbortController()
    setResult(null)
    setStatus(null)
    void loadRule(locationId, controller.signal)
    return () => controller.abort()
  }, [locationId, loadRule])

  async function save() {
    setPending('save')
    setError(null)
    setStatus(null)
    try {
      const rule = await saveAutomationRule(locationId, selectedKey)
      setSavedKey(rule.strategy_key)
      setPersisted(true)
      setStatus(`Saved ${rule.strategy_key}.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the strategy.')
    } finally {
      setPending(null)
    }
  }

  async function evaluate() {
    setPending('evaluate')
    setError(null)
    setStatus(null)
    try {
      setResult(await evaluateAutomation(locationId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not evaluate.')
    } finally {
      setPending(null)
    }
  }

  const unsaved = selectedKey !== savedKey
  const chosen = strategies.find((option) => option.key === selectedKey)

  if (locations.length === 0) {
    return (
      <p className="text-sm text-ink-soft">
        No locations yet. Create one in Configuration and its zones will be evaluated here.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm text-ink-soft">
          Location
          <select
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
            className="rounded-lg border border-line bg-white px-2 py-1.5 text-sm"
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-ink-soft">
          Strategy
          <select
            value={selectedKey}
            onChange={(event) => setSelectedKey(event.target.value)}
            className="rounded-lg border border-line bg-white px-2 py-1.5 text-sm"
          >
            {strategies.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => void save()}
          disabled={pending !== null || !selectedKey}
          className="rounded-lg bg-moss-500 px-3 py-1.5 text-sm text-white transition-colors hover:bg-moss-700 disabled:opacity-50"
        >
          {pending === 'save' ? 'Saving…' : 'Save'}
        </button>

        <button
          type="button"
          onClick={() => void evaluate()}
          disabled={pending !== null || !locationId}
          className="rounded-lg border border-moss-500 px-3 py-1.5 text-sm text-moss-700 transition-colors hover:bg-moss-50 disabled:opacity-50"
        >
          {pending === 'evaluate' ? 'Evaluating…' : 'Evaluate'}
        </button>
      </div>

      {chosen && <p className="text-sm text-ink-soft">{chosen.description}</p>}

      {!persisted && savedKey && (
        <p className="text-sm text-ink-soft">
          Nothing saved for this location yet, so evaluate uses {savedKey} by default.
        </p>
      )}

      {unsaved && (
        <p className="text-sm text-sun-500">
          Save before evaluating. Evaluate uses the saved strategy, not the dropdown.
        </p>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-clay-50 px-3 py-2 text-sm text-clay-500">
          {error}
        </p>
      )}

      {status && <p className="rounded-lg bg-moss-50 px-3 py-2 text-sm text-moss-700">{status}</p>}

      {result && (
        <div className="rounded-lg border border-line p-4">
          <div className="flex flex-wrap items-center gap-2">
            <ActionBadge action={result.action} />
            <span className="text-xs text-ink-soft">decided by {result.strategy_key}</span>
          </div>
          <p className="mt-2 text-sm">{result.reason}</p>

          {result.zones.length > 0 && (
            <ul className="mt-2 divide-y divide-line">
              {result.zones.map((zone) => (
                <ZoneResult key={zone.zone_id} zone={zone} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}