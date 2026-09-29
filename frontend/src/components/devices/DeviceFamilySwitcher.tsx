import type { DeviceFamily } from '../../services/api'

const FAMILIES: { key: DeviceFamily; label: string }[] = [
  { key: 'simulation', label: 'Simulation' },
  { key: 'edge', label: 'Edge hardware' },
]

/** Two buttons that pick which family the list and the provision button use. */
export default function DeviceFamilySwitcher({
  value,
  onChange,
  disabled = false,
}: {
  value: DeviceFamily
  onChange: (family: DeviceFamily) => void
  disabled?: boolean
}) {
  return (
    <div
      role="group"
      aria-label="Device family"
      className="inline-flex rounded-lg border border-line bg-white p-1"
    >
      {FAMILIES.map(({ key, label }) => {
        const selected = key === value
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            disabled={disabled}
            aria-pressed={selected}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors disabled:opacity-50 ${
              selected ? 'bg-moss-500 text-white' : 'text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
