import type { ReactNode } from 'react'

import DeviceList from '../components/devices/DeviceList'
import SensorList from '../features/sensors/SensorList'

/**
 * Placeholder sections for the greenhouse dashboard.
 *
 * The `id` on each section is a contract with later phases: Phase 2 filled
 * #sensors, Phase 3 filled #devices, and the rest follow.
 */
type Section = {
  id: string
  title: string
  summary: string
  arriving: string
}

const sections: Section[] = [
  {
    id: 'overview',
    title: 'Overview',
    summary: 'Temperature, humidity and light for the whole greenhouse at a glance.',
    arriving: 'A later phase',
  },
  {
    id: 'sensors',
    title: 'Sensors',
    summary: 'Live readings from every connected device, one row per sensor.',
    arriving: 'Phase 2 — Factory Method',
  },
  {
    id: 'devices',
    title: 'Devices',
    summary: 'Matching kits of sensors and actuators, one family at a time.',
    arriving: 'Phase 3 — Abstract Factory',
  },
  {
    id: 'configuration',
    title: 'Configuration',
    summary: 'Thresholds, units and calibration for each device.',
    arriving: 'A later phase',
  },
  {
    id: 'automation',
    title: 'Automation',
    summary: 'Rules that decide when to water, vent or switch on the lamps.',
    arriving: 'A later phase',
  },
  {
    id: 'controls',
    title: 'Controls',
    summary: 'Manual overrides for pumps, vents and lighting.',
    arriving: 'A later phase',
  },
  {
    id: 'events',
    title: 'Events',
    summary: 'A running log of what the greenhouse did, and what triggered it.',
    arriving: 'A later phase',
  },
]

const WIDE = new Set(['overview', 'sensors', 'devices'])

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-semibold text-moss-700">Dashboard</h1>
        <p className="max-w-xl text-ink-soft">
          Sensors and device families are live. The remaining sections are reserved for the phase
          that builds them.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sections.map((section) => (
          <SectionCard key={section.id} section={section} />
        ))}
      </div>
    </div>
  )
}

function SectionCard({ section }: { section: Section }) {
  return (
    <section
      id={section.id}
      aria-labelledby={`${section.id}-title`}
      className={`flex flex-col gap-3 rounded-xl border border-line bg-white p-5 ${
        WIDE.has(section.id) ? 'sm:col-span-2 lg:col-span-3' : ''
      }`}
    >
      <h2 id={`${section.id}-title`} className="font-display text-lg font-semibold">
        {section.title}
      </h2>
      {section.id === 'sensors' ? (
        <SensorList />
      ) : section.id === 'devices' ? (
        <DeviceList />
      ) : (
        <>
          <p className="text-sm text-ink-soft">{section.summary}</p>
          <Tag>{section.arriving}</Tag>
        </>
      )}
    </section>
  )
}

function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="mt-auto w-fit rounded-md bg-glass-100 px-2 py-1 text-xs text-ink-soft">
      {children}
    </span>
  )
}