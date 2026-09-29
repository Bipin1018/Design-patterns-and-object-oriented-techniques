import { useCallback, useEffect, useState } from 'react'

import {
  addZone,
  createLocationConfig,
  deleteLocation,
  deleteZone,
  fetchLocationConfig,
  fetchLocations,
  fetchZoneDevices,
  updateZone,
  type DeviceDto,
  type LocationConfigDto,
  type LocationSummaryDto,
  type ZoneDto,
  type ZoneInput,
} from '../../services/api'

/** A zone being typed in. Kept as strings so a half-typed number is allowed. */
type ZoneDraft = {
  name: string
  low: string
  high: string
  schedule: string
}

const EMPTY_DRAFT: ZoneDraft = { name: '', low: '0.2', high: '0.45', schedule: '' }

/**
 * Checks a draft before it is sent. The same rules run on the server in
 * build(); this copy exists only to catch mistakes without a round trip.
 */
function checkDraft(draft: ZoneDraft): string | null {
  if (!draft.name.trim()) return 'Zone name is required.'

  const low = Number(draft.low)
  const high = Number(draft.high)
  if (Number.isNaN(low) || Number.isNaN(high)) return 'Thresholds must be numbers.'
  if (low < 0 || low > 1 || high < 0 || high > 1) return 'Thresholds must be between 0 and 1.'
  if (low >= high) return 'Low threshold must be below high threshold.'

  if (draft.schedule.trim()) {
    try {
      JSON.parse(draft.schedule)
    } catch {
      return 'Schedule must be valid JSON, for example {"watering": "08:00"}.'
    }
  }
  return null
}

function draftToInput(draft: ZoneDraft): ZoneInput {
  return {
    name: draft.name.trim(),
    moisture_threshold_low: Number(draft.low),
    moisture_threshold_high: Number(draft.high),
    schedule: draft.schedule.trim()
      ? (JSON.parse(draft.schedule) as Record<string, unknown>)
      : {},
  }
}

function zoneToDraft(zone: ZoneDto): ZoneDraft {
  return {
    name: zone.name,
    low: String(zone.moisture_threshold_low),
    high: String(zone.moisture_threshold_high),
    schedule: Object.keys(zone.schedule).length ? JSON.stringify(zone.schedule) : '',
  }
}

export default function LocationConfigWizard({ onChange }: { onChange?: () => void }) {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [config, setConfig] = useState<LocationConfigDto | null>(null)
  const [zoneDevices, setZoneDevices] = useState<Record<string, DeviceDto[]>>({})
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const report = useCallback(
    (caught: unknown, fallback: string) => {
      setError(caught instanceof Error ? caught.message : fallback)
    },
    [],
  )

  const loadLocations = useCallback(async (signal?: AbortSignal) => {
    try {
      setLocations(await fetchLocations(signal))
    } catch (caught) {
      if (!signal?.aborted) report(caught, 'Could not load locations.')
    }
  }, [report])

  const loadConfig = useCallback(
    async (locationId: string) => {
      try {
        const loaded = await fetchLocationConfig(locationId)
        setConfig(loaded)
        setError(null)

        const pairs = await Promise.all(
          loaded.zones.map(async (zone) => {
            const devices = await fetchZoneDevices(locationId, zone.id)
            return [zone.id, devices] as const
          }),
        )
        setZoneDevices(Object.fromEntries(pairs))
      } catch (caught) {
        report(caught, 'Could not load that location.')
      }
    },
    [report],
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadLocations(controller.signal)
    return () => controller.abort()
  }, [loadLocations])

  useEffect(() => {
    if (selectedId) void loadConfig(selectedId)
    else {
      setConfig(null)
      setZoneDevices({})
    }
  }, [selectedId, loadConfig])

  /** Run a write, then refresh whatever it touched. */
  async function run(action: () => Promise<void>, success: string) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await action()
      setNotice(success)
      onChange?.()
    } catch (caught) {
      report(caught, 'The request failed.')
    } finally {
      setBusy(false)
    }
  }

  async function handleCreate(name: string, drafts: ZoneDraft[]) {
    await run(async () => {
      const created = await createLocationConfig(name.trim(), drafts.map(draftToInput))
      await loadLocations()
      setSelectedId(created.location.id) // new location becomes the selection
    }, 'Location created.')
  }

  async function handleDeleteLocation(location: LocationSummaryDto) {
    if (!window.confirm(`Delete "${location.name}" and all of its zones?`)) return

    await run(async () => {
      await deleteLocation(location.id)
      await loadLocations()
      if (selectedId === location.id) setSelectedId(null) // clears the zone list too
    }, 'Location deleted.')
  }

  async function handleAddZone(draft: ZoneDraft) {
    if (!selectedId) return
    await run(async () => {
      await addZone(selectedId, draftToInput(draft))
      await loadConfig(selectedId)
    }, 'Zone added.')
  }

  async function handleUpdateZone(zoneId: string, draft: ZoneDraft) {
    if (!selectedId) return
    await run(async () => {
      await updateZone(selectedId, zoneId, draftToInput(draft))
      await loadConfig(selectedId)
    }, 'Zone updated.')
  }

  async function handleDeleteZone(zone: ZoneDto) {
    if (!selectedId) return
    if (!window.confirm(`Delete zone "${zone.name}"? Its devices become unassigned.`)) return

    await run(async () => {
      await deleteZone(selectedId, zone.id)
      await loadConfig(selectedId)
    }, 'Zone deleted.')
  }

  return (
    <div className="space-y-6">
      {error && (
        <p role="alert" className="rounded-lg bg-clay-50 px-3 py-2 text-sm text-clay-500">
          {error}
        </p>
      )}
      {notice && !error && (
        <p className="rounded-lg bg-moss-50 px-3 py-2 text-sm text-moss-700">{notice}</p>
      )}

      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <div className="space-y-4">
          <section className="space-y-2">
            <h3 className="font-display font-semibold">Saved locations</h3>
            {locations.length === 0 ? (
              <p className="text-sm text-ink-soft">None yet. Create one below.</p>
            ) : (
              <ul className="space-y-1">
                {locations.map((location) => (
                  <li key={location.id} className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedId(location.id)}
                      className={`flex-1 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                        selectedId === location.id
                          ? 'bg-moss-50 text-moss-700'
                          : 'text-ink-soft hover:text-ink'
                      }`}
                    >
                      {location.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteLocation(location)}
                      disabled={busy}
                      className="rounded-md px-2 py-1 text-xs text-clay-500 hover:bg-clay-50 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <CreateLocationForm busy={busy} onCreate={handleCreate} />
        </div>

        <div className="space-y-4">
          {!config ? (
            <p className="text-sm text-ink-soft">
              Select a location to see its zones, or create one.
            </p>
          ) : (
            <>
              <header>
                <h3 className="font-display text-lg font-semibold">{config.location.name}</h3>
                <p className="text-xs text-ink-soft">location id {config.location.id}</p>
              </header>

              <ul className="space-y-3">
                {config.zones.map((zone) => (
                  <ZoneCard
                    key={zone.id}
                    zone={zone}
                    devices={zoneDevices[zone.id] ?? []}
                    busy={busy}
                    canDelete={config.zones.length > 1}
                    onSave={(draft) => void handleUpdateZone(zone.id, draft)}
                    onDelete={() => void handleDeleteZone(zone)}
                  />
                ))}
              </ul>

              <AddZoneForm busy={busy} onAdd={handleAddZone} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function CreateLocationForm({
  busy,
  onCreate,
}: {
  busy: boolean
  onCreate: (name: string, drafts: ZoneDraft[]) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [drafts, setDrafts] = useState<ZoneDraft[]>([{ ...EMPTY_DRAFT }])
  const [problem, setProblem] = useState<string | null>(null)

  function update(index: number, patch: Partial<ZoneDraft>) {
    setDrafts((current) => current.map((d, i) => (i === index ? { ...d, ...patch } : d)))
  }

  function submit() {
    if (!name.trim()) {
      setProblem('Location name is required.')
      return
    }
    if (drafts.length === 0) {
      setProblem('A location needs at least one zone.')
      return
    }
    for (const draft of drafts) {
      const found = checkDraft(draft)
      if (found) {
        setProblem(found)
        return
      }
    }
    setProblem(null)
    void onCreate(name, drafts).then(() => {
      setName('')
      setDrafts([{ ...EMPTY_DRAFT }])
    })
  }

  return (
    <section className="space-y-3 rounded-lg border border-line p-3">
      <h3 className="font-display font-semibold">New location</h3>

      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Location name"
        className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
      />

      {drafts.map((draft, index) => (
        <ZoneFields
          key={index}
          draft={draft}
          onChange={(patch) => update(index, patch)}
          onRemove={drafts.length > 1 ? () => setDrafts((c) => c.filter((_, i) => i !== index)) : undefined}
        />
      ))}

      {problem && <p className="text-xs text-clay-500">{problem}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setDrafts((current) => [...current, { ...EMPTY_DRAFT }])}
          className="rounded-md border border-line px-2 py-1 text-xs text-ink-soft hover:text-ink"
        >
          Add another zone
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="rounded-md bg-moss-500 px-3 py-1 text-xs text-white hover:bg-moss-700 disabled:opacity-50"
        >
          Create location
        </button>
      </div>
    </section>
  )
}

function AddZoneForm({
  busy,
  onAdd,
}: {
  busy: boolean
  onAdd: (draft: ZoneDraft) => Promise<void>
}) {
  const [draft, setDraft] = useState<ZoneDraft>({ ...EMPTY_DRAFT })
  const [problem, setProblem] = useState<string | null>(null)

  function submit() {
    const found = checkDraft(draft)
    setProblem(found)
    if (found) return
    void onAdd(draft).then(() => setDraft({ ...EMPTY_DRAFT }))
  }

  return (
    <section className="space-y-3 rounded-lg border border-line p-3">
      <h4 className="font-display font-semibold">Add a zone</h4>
      <ZoneFields draft={draft} onChange={(patch) => setDraft((c) => ({ ...c, ...patch }))} />
      {problem && <p className="text-xs text-clay-500">{problem}</p>}
      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="rounded-md bg-moss-500 px-3 py-1 text-xs text-white hover:bg-moss-700 disabled:opacity-50"
      >
        Add zone
      </button>
    </section>
  )
}

function ZoneCard({
  zone,
  devices,
  busy,
  canDelete,
  onSave,
  onDelete,
}: {
  zone: ZoneDto
  devices: DeviceDto[]
  busy: boolean
  canDelete: boolean
  onSave: (draft: ZoneDraft) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<ZoneDraft>(() => zoneToDraft(zone))
  const [problem, setProblem] = useState<string | null>(null)

  function save() {
    const found = checkDraft(draft)
    setProblem(found)
    if (found) return
    onSave(draft)
    setEditing(false)
  }

  return (
    <li className="rounded-lg border border-line p-3">
      {editing ? (
        <div className="space-y-2">
          <ZoneFields draft={draft} onChange={(patch) => setDraft((c) => ({ ...c, ...patch }))} />
          {problem && <p className="text-xs text-clay-500">{problem}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="rounded-md bg-moss-500 px-3 py-1 text-xs text-white hover:bg-moss-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setDraft(zoneToDraft(zone))
                setProblem(null)
                setEditing(false)
              }}
              className="rounded-md border border-line px-3 py-1 text-xs text-ink-soft"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-medium">{zone.name}</span>
            <span className="text-xs text-ink-soft">
              {zone.moisture_threshold_low} – {zone.moisture_threshold_high} vwc
            </span>
            <span className="ml-auto flex gap-2">
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="text-xs text-moss-700 hover:underline"
              >
                Edit
              </button>
              <button
                type="button"
                onClick={onDelete}
                disabled={busy || !canDelete}
                title={canDelete ? undefined : 'A location must keep at least one zone.'}
                className="text-xs text-clay-500 hover:underline disabled:opacity-40 disabled:hover:no-underline"
              >
                Delete
              </button>
            </span>
          </div>
          {Object.keys(zone.schedule).length > 0 && (
            <p className="text-xs text-ink-soft">schedule {JSON.stringify(zone.schedule)}</p>
          )}
          <p className="text-xs text-ink-soft">
            {devices.length === 0
              ? 'No devices in this zone.'
              : `Devices: ${devices.map((d) => d.display_name).join(', ')}`}
          </p>
        </div>
      )}
    </li>
  )
}

function ZoneFields({
  draft,
  onChange,
  onRemove,
}: {
  draft: ZoneDraft
  onChange: (patch: Partial<ZoneDraft>) => void
  onRemove?: () => void
}) {
  return (
    <div className="space-y-2 rounded-md bg-glass-100 p-2">
      <div className="flex gap-2">
        <input
          value={draft.name}
          onChange={(event) => onChange({ name: event.target.value })}
          placeholder="Zone name"
          className="flex-1 rounded-md border border-line px-2 py-1 text-sm"
        />
        {onRemove && (
          <button type="button" onClick={onRemove} className="text-xs text-clay-500">
            Remove
          </button>
        )}
      </div>
      <div className="flex gap-2">
        <label className="flex-1 text-xs text-ink-soft">
          low
          <input
            value={draft.low}
            onChange={(event) => onChange({ low: event.target.value })}
            inputMode="decimal"
            className="w-full rounded-md border border-line px-2 py-1 text-sm"
          />
        </label>
        <label className="flex-1 text-xs text-ink-soft">
          high
          <input
            value={draft.high}
            onChange={(event) => onChange({ high: event.target.value })}
            inputMode="decimal"
            className="w-full rounded-md border border-line px-2 py-1 text-sm"
          />
        </label>
      </div>
      <input
        value={draft.schedule}
        onChange={(event) => onChange({ schedule: event.target.value })}
        placeholder='schedule JSON, e.g. {"watering": "08:00"}'
        className="w-full rounded-md border border-line px-2 py-1 text-xs"
      />
    </div>
  )
}