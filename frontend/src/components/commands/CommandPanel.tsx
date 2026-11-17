import { useCallback, useEffect, useState } from 'react'

import {
  fetchCommands,
  fetchDevices,
  runCommand,
  type CommandLogDto,
  type CommandStatus,
  type CommandType,
  type DeviceDto,
} from '../../services/api'
import { StateBadge } from '../devices/ActuatorStateBadge'

type Status = 'loading' | 'ready' | 'error'
type Notice = { text: string; ok: boolean }

const HISTORY_LIMIT = 50
const DEFAULT_LEVEL = 1

/** The buttons. Which ones are enabled comes from allowed_commands, never from here. */
const BUTTONS: { type: CommandType; label: string }[] = [
  { type: 'start_pump', label: 'Start pump' },
  { type: 'stop_pump', label: 'Stop pump' },
  { type: 'set_light_level', label: 'Set light level' },
]

const STATUS_TONES: Record<CommandStatus, string> = {
  success: 'bg-moss-50 text-moss-700',
  failed: 'bg-clay-50 text-clay-500',
  rejected: 'bg-sun-50 text-sun-500',
}

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}

function nameOf(device: DeviceDto): string {
  return device.display_name || device.device_type
}

function readable(command: string): string {
  return command.replace(/_/g, ' ')
}

function StatusBadge({ status }: { status: CommandStatus }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_TONES[status]}`}>
      {status}
    </span>
  )
}

/**
 * Phase 10 controls. Each button sends a command to POST /api/commands.
 * After every click the actuators and the history are loaded again, so the
 * buttons follow the new allowed_commands. onChange lets the rest of the
 * dashboard (device states, execution log) reload too.
 */
export default function CommandPanel({ onChange }: { onChange?: () => void }) {
  const [actuators, setActuators] = useState<DeviceDto[]>([])
  const [history, setHistory] = useState<CommandLogDto[]>([])
  const [levels, setLevels] = useState<Record<string, number>>({})
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [devices, rows] = await Promise.all([
        fetchDevices({ role: 'actuator' }, signal),
        fetchCommands(HISTORY_LIMIT, signal),
      ])
      setActuators(devices)
      setHistory(rows)
      setStatus('ready')
      setError(null)
    } catch (caught) {
      if (signal?.aborted) return
      setStatus('error')
      setError(errorText(caught, 'Could not load the controls.'))
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function send(device: DeviceDto, type: CommandType) {
    const payload =
      type === 'set_light_level' ? { level: levels[device.id] ?? DEFAULT_LEVEL } : {}

    setPending(`${device.id}:${type}`)
    setNotice(null)
    try {
      const row = await runCommand(type, device.id, payload)
      setNotice(
        row.status === 'success'
          ? { text: `${readable(type)}: success.`, ok: true }
          : { text: `${readable(type)}: ${row.status}. ${row.error_message ?? ''}`, ok: false },
      )
    } catch (caught) {
      setNotice({ text: errorText(caught, 'Could not send the command.'), ok: false })
    } finally {
      setPending(null)
      await load()
      onChange?.()
    }
  }

  const names = new Map(actuators.map((device) => [device.id, nameOf(device)]))
  // Only the simulation family has an adapter, as in Phase 9.
  const drivable = actuators.filter((device) => device.device_family === 'simulation')

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-ink-soft">
        Each button sends a command object to the backend. A button is disabled when its command
        is not in the actuator's <code className="font-mono">allowed_commands</code>. Every
        command is saved in the history below as <strong>success</strong>,{' '}
        <strong>failed</strong> or <strong>rejected</strong>.
      </p>

      {error && (
        <p role="alert" className="text-sm text-clay-500">
          {error}
        </p>
      )}

      {status === 'loading' ? (
        <p className="text-sm text-ink-soft">Loading actuators…</p>
      ) : drivable.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-ink-soft">
          No simulation actuators. Provision a simulation kit in Devices first.
        </p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line">
          {drivable.map((device) => (
            <li key={device.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
              <span className="min-w-40 text-sm font-medium">{nameOf(device)}</span>
              {device.state && (
                <StateBadge state={device.state} allowedCommands={device.allowed_commands} />
              )}
              <div className="ml-auto flex flex-wrap items-center gap-2">
                {BUTTONS.map(({ type, label }) => {
                  const allowed = device.allowed_commands.includes(type)
                  const busy = pending === `${device.id}:${type}`
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => void send(device, type)}
                      disabled={!allowed || pending !== null}
                      title={allowed ? undefined : `Not allowed while ${device.state ?? 'unknown'}`}
                      className="rounded-md bg-moss-700 px-3 py-1.5 text-sm text-white disabled:opacity-40"
                    >
                      {busy ? 'Sending…' : label}
                    </button>
                  )
                })}
                <label className="flex items-center gap-1 text-xs text-ink-soft">
                  Level
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={levels[device.id] ?? DEFAULT_LEVEL}
                    onChange={(event) =>
                      setLevels((current) => ({
                        ...current,
                        [device.id]: Number(event.target.value),
                      }))
                    }
                    disabled={pending !== null}
                    className="w-16 rounded-md border border-line bg-white px-2 py-1 text-sm text-ink"
                  />
                </label>
              </div>
            </li>
          ))}
        </ul>
      )}

      {notice && (
        <p
          role={notice.ok ? 'status' : 'alert'}
          className={`text-sm ${notice.ok ? 'text-moss-700' : 'text-clay-500'}`}
        >
          {notice.text}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-base font-semibold">Command history</h3>
        <button
          type="button"
          onClick={() => void load()}
          disabled={pending !== null}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-soft disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {history.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-ink-soft">
          No commands yet. Use a button above to send the first one.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-left text-sm">
            <thead className="bg-glass-100 text-xs text-ink-soft">
              <tr>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Command</th>
                <th className="px-3 py-2 font-medium">Device</th>
                <th className="px-3 py-2 font-medium">Payload</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {history.map((row) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-soft">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.command_type}</td>
                  <td className="px-3 py-2">
                    {names.get(row.device_id) ?? row.device_id.slice(0, 8)}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{JSON.stringify(row.payload)}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-3 py-2 text-ink-soft">{row.error_message ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}