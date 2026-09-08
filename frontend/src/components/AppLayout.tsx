import { NavLink, Outlet } from 'react-router-dom'

import { API_BASE_URL } from '../services/api'
import HealthStatus from './HealthStatus'

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-line bg-glass-50/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-3">
          <NavLink to="/" className="flex items-center gap-2.5">
            <Mark />
            <span className="font-display text-xl leading-none font-semibold text-moss-700">
              Smart Greenhouse
            </span>
          </NavLink>

          <nav className="flex items-center gap-1 text-sm">
            <NavItem to="/">Home</NavItem>
            <NavItem to="/dashboard">Dashboard</NavItem>
          </nav>

          <div className="ml-auto">
            <HealthStatus />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl grow px-5 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-line px-5 py-4 text-center text-xs text-ink-soft">
        Phase 1 skeleton · API at {API_BASE_URL}
      </footer>
    </div>
  )
}

function NavItem({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `rounded-md px-2.5 py-1.5 transition-colors ${
          isActive ? 'bg-moss-50 text-moss-700' : 'text-ink-soft hover:text-ink'
        }`
      }
    >
      {children}
    </NavLink>
  )
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className="size-7" fill="none">
      <path
        d="M4 13.5 16 4.5l12 9V27a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V13.5Z"
        stroke="currentColor"
        className="text-moss-500"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M16 4.5V28M4 19h24"
        stroke="currentColor"
        className="text-moss-300"
        strokeWidth="1.25"
      />
    </svg>
  )
}
