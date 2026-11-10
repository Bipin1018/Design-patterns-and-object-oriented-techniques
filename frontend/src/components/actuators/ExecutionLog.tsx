import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  applyActuatorCommand,
  fetchDevices,
  fetchExecutions,
  type DeviceDto,
  type ExecutionDto,
} from '../../services/api'

type Status = 'loading' | 'ready' | 'error'
type Notice = { text: string; ok: boolean }

const LIMIT = 20

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}

function nameOf(device: DeviceDto): string {
  return device.display_name || device.device_type
}

function ResultBadge({ success }: { success: boolean }) {
  const tone = success ? 'bg-moss-50 text-moss-700' : 'bg-clay-50 text-clay-500'
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${tone}`}>
      {success ? 'success' : 'failed'}
    </span>
  )
}

export default function ExecutionLog() {
  const [rows, setRows] = useState<ExecutionDto[]>([])
  const [actuators, setActuators] = useState<DeviceDto[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)
  const [deviceId, setDeviceId] = useState('')
  const [command, setCommand] = useState('start_pump')
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [executions, devices] = await Promise.all([
        fetchExecutions(LIMIT, signal),
        fetchDevices({ role: 'actuator' }, signal),
      ])
      setRows(executions)
      setActuators(devices)
      // Default to the first actuator the simulation adapter can drive.
      setDeviceId(
        (current) => current || devices.find((d) => d.device_family === 'simulation')?.id || '',
      )
      setStatus('ready')
      setError(null)
    } catch (caught) {
      if (signal?.aborted) return
      setStatus('error')
      setError(errorText(caught, 'Could not load the execution log.'))
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function apply(event: FormEvent) {
    event.preventDefault()
    if (!deviceId || !command.trim()) return

    setPending(true)
    setNotice(null)
    try {
      await applyActuatorCommand(deviceId, command.trim())
      setNotice({ text: 'Applied. A success row was added.', ok: true })
    } catch (caught) {
      // 409 means a policy blocked it. The row is already in the log.
      setNotice({ text: errorText(caught, 'Could not apply the command.'), ok: false })
    } finally {
      setPending(false)
      await load()
    }
  }

  const names = new Map(actuators.map((device) => [device.id, nameOf(device)]))
  const drivable = actuators.filter((device) => device.device_family === 'simulation')

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-ink-soft">
        Commands go through the decorated actuator port: logging, then max run time, then the
        adapter. The command name is not checked yet, so any command succeeds until the actuator
        has been <strong>running</strong> for 30 minutes. A success row has an empty message and
        policy <code className="font-mono">logging</code>. A blocked row shows{' '}
        <em>Max run time exceeded</em> with policies{' '}
        <code className="font-mono">maxRunTime</code> and{' '}
        <code className="font-mono">logging</code>.
      </p>

      <form onSubmit={(event) => void apply(event)} className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-ink-soft">
          Actuator
          <select
            value={deviceId}
            onChange={(event) => setDeviceId(event.target.value)}
            disabled={pending || drivable.length === 0}
            className="rounded-md border border-line bg-white px-2 py-1 text-sm text-ink"
          >
            {drivable.length === 0 && <option value="">No simulation actuators</option>}
            {drivable.map((device) => (
              <option key={device.id} value={device.id}>
                {nameOf(device)} ({device.state ?? 'unknown'})
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-ink-soft">
          Command
          <input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            disabled={pending}
            className="rounded-md border border-line bg-white px-2 py-1 font-mono text-sm text-ink"
          />
        </label>

        <button
          type="submit"
          disabled={pending || !deviceId || !command.trim()}
          className="rounded-md bg-moss-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {pending ? 'Applying…' : 'Apply'}
        </button>
        <button
          type="button"
          onClick={() => void load()}
          disabled={pending}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-soft disabled:opacity-50"
        >
          Refresh
        </button>
      </form>

      {notice && (
        <p
          role={notice.ok ? 'status' : 'alert'}
          className={`text-sm ${notice.ok ? 'text-moss-700' : 'text-clay-500'}`}
        >
          {notice.text}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-clay-500">
          {error}
        </p>
      )}

      {status === 'loading' ? (
        <p className="text-sm text-ink-soft">Loading execution log…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-ink-soft">
          No executions yet. Apply a command above to add the first row.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-left text-sm">
            <thead className="bg-glass-100 text-xs text-ink-soft">
              <tr>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Device</th>
                <th className="px-3 py-2 font-medium">Result</th>
                <th className="px-3 py-2 font-medium">Policies</th>
                <th className="px-3 py-2 font-medium">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-soft">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    {names.get(row.device_id) ?? row.device_id.slice(0, 8)}
                  </td>
                  <td className="px-3 py-2">
                    <ResultBadge success={row.success} />
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {row.policy_applied.map((policy) => (
                        <span
                          key={policy}
                          className="rounded bg-glass-100 px-1.5 py-0.5 font-mono text-xs"
                        >
                          {policy}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-ink-soft">{row.message ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}