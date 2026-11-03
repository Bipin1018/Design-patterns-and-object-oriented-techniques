import { useState } from 'react'

import { transitionActuator, type ActuatorStateName, type DeviceDto } from '../../services/api'

/** Badge colours from the guided check. off isn't listed there, so it gets neutral zinc. */
const TONES: Record<ActuatorStateName, string> = {
  idle: 'bg-slate-100 text-slate-700',
  running: 'bg-emerald-100 text-emerald-700',
  error: 'bg-red-100 text-red-700',
  maintenance: 'bg-amber-100 text-amber-800',
  off: 'bg-zinc-200 text-zinc-600',
}

/**
 * The names the demo picker offers. This is vocabulary, not rules: every choice
 * goes to the backend, and the domain decides whether the move is legal.
 */
const TARGETS: ActuatorStateName[] = ['idle', 'running', 'off', 'maintenance', 'error']

function readable(command: string): string {
  return command.replace(/_/g, ' ')
}

function errorText(caught: unknown): string {
  return caught instanceof Error ? caught.message : 'Could not change the state.'
}

export function StateBadge({
  state,
  allowedCommands,
}: {
  state: ActuatorStateName
  allowedCommands: string[]
}) {
  const tooltip =
    allowedCommands.length > 0
      ? `Allowed now: ${allowedCommands.map(readable).join(', ')}`
      : 'No commands are allowed in this state'

  return (
    <span
      title={tooltip}
      className={`cursor-help rounded px-1.5 py-0.5 text-xs font-medium ${TONES[state]}`}
    >
      {state}
    </span>
  )
}

type Props = {
  device: DeviceDto
  /** Called after a successful move, so the list re-reads the devices from the API. */
  onChanged: () => void
}

export default function ActuatorStateBadge({ device, onChanged }: Props) {
  const [target, setTarget] = useState<ActuatorStateName>('running')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (device.role !== 'actuator' || device.state === null) return null

  async function move() {
    setPending(true)
    setError(null)
    try {
      await transitionActuator(device.id, target)
      onChanged()
    } catch (caught) {
      // A 409 carries the domain's own sentence, e.g. "Cannot go from running to maintenance…"
      setError(errorText(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="mt-1 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={device.state} allowedCommands={device.allowed_commands} />
        <span className="text-xs text-ink-soft">
          {device.allowed_commands.length > 0
            ? `can: ${device.allowed_commands.map(readable).join(' · ')}`
            : 'no commands available'}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`transition-${device.id}`} className="text-xs text-ink-soft">
          Demo move to
        </label>
        <select
          id={`transition-${device.id}`}
          value={target}
          onChange={(event) => setTarget(event.target.value as ActuatorStateName)}
          disabled={pending}
          className="rounded-md border border-line bg-white px-1.5 py-0.5 text-xs"
        >
          {TARGETS.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => void move()}
          disabled={pending}
          className="rounded-md bg-moss-700 px-2 py-0.5 text-xs text-white disabled:opacity-50"
        >
          {pending ? 'Moving…' : 'Move'}
        </button>
      </div>

      {error && (
        <p role="alert" className="text-xs text-clay-500">
          {error}
        </p>
      )}
    </div>
  )
}