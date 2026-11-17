import { useCallback, useEffect, useState } from 'react'

import {
  fetchDevices,
  fetchExecutions,
  type DeviceDto,
  type ExecutionDto,
} from '../../services/api'

type Status = 'loading' | 'ready' | 'error'

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

/**
 * Phase 9 execution log, read only. Commands are sent from CommandPanel (Phase 10).
 * refreshKey goes up after every command, so the table reloads with the new row.
 */
export default function ExecutionLog({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<ExecutionDto[]>([])
  const [actuators, setActuators] = useState<DeviceDto[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [executions, devices] = await Promise.all([
        fetchExecutions(LIMIT, signal),
        fetchDevices({ role: 'actuator' }, signal),
      ])
      setRows(executions)
      setActuators(devices)
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
  }, [load, refreshKey])

  const names = new Map(actuators.map((device) => [device.id, nameOf(device)]))

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-base font-semibold">Execution log</h3>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-soft"
        >
          Refresh
        </button>
      </div>
      <p className="max-w-3xl text-sm text-ink-soft">
        Every command that reached the decorated actuator port: logging, then max run time, then
        the adapter. A blocked row shows <em>Max run time exceeded</em> with policies{' '}
        <code className="font-mono">maxRunTime</code> and{' '}
        <code className="font-mono">logging</code>. Rejected commands never reach the port, so
        they appear only in the command history above.
      </p>

      {error && (
        <p role="alert" className="text-sm text-clay-500">
          {error}
        </p>
      )}

      {status === 'loading' ? (
        <p className="text-sm text-ink-soft">Loading execution log…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-ink-soft">
          No executions yet. Send a command above to add the first row.
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