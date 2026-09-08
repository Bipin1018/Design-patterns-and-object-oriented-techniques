import { Link } from 'react-router-dom'

import { API_BASE_URL } from '../services/api'

const links = [
  { href: `${API_BASE_URL}/scalar`, label: 'API reference', hint: 'Scalar' },
  { href: `${API_BASE_URL}/openapi.json`, label: 'OpenAPI schema', hint: 'JSON' },
  { href: `${API_BASE_URL}/health`, label: 'Health check', hint: 'JSON' },
]

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="font-display text-4xl leading-tight font-semibold text-moss-700">
          Keep the greenhouse in range
        </h1>
        <p className="max-w-xl text-lg text-ink-soft">
          A three-tier project: FastAPI over PostgreSQL, with this React dashboard on top. Phase
          1 stands the stack up and proves every layer can reach the next one.
        </p>
        <Link
          to="/dashboard"
          className="inline-block rounded-lg bg-moss-500 px-4 py-2 text-white transition-colors hover:bg-moss-700"
        >
          Open the dashboard
        </Link>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl font-semibold">While the stack is running</h2>
        <ul className="grid gap-3 sm:grid-cols-3">
          {links.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="block rounded-xl border border-line bg-white p-4 transition-colors hover:border-moss-300"
              >
                <span className="block text-moss-700">{link.label}</span>
                <span className="text-sm text-ink-soft">{link.hint}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
