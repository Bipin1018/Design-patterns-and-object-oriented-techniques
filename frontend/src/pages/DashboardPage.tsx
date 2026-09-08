import type { ReactNode } from 'react'
type Section = {
  id: string
  title: string
  summary: string
  arriving: string
  next?: boolean
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
    next: true,
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

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-semibold text-moss-700">Dashboard</h1>
        <p className="max-w-xl text-ink-soft">
          Nothing is wired to a greenhouse yet. Each section below is reserved for the phase
          that builds it.
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
      className={`flex flex-col gap-3 rounded-xl border p-5 ${
        section.next ? 'border-moss-300 bg-moss-50' : 'border-line bg-white'
      } ${section.id === 'overview' ? 'sm:col-span-2 lg:col-span-3' : ''}`}
    >
      <h2 id={`${section.id}-title`} className="font-display text-lg font-semibold">
        {section.title}
      </h2>
      <p className="text-sm text-ink-soft">{section.summary}</p>
      <Tag highlight={section.next}>{section.arriving}</Tag>
    </section>
  )
}

function Tag({ children, highlight }: { children: ReactNode; highlight?: boolean }) {
  return (
    <span
      className={`mt-auto w-fit rounded-md px-2 py-1 text-xs ${
        highlight ? 'bg-moss-500 text-white' : 'bg-glass-100 text-ink-soft'
      }`}
    >
      {children}
    </span>
  )
}
