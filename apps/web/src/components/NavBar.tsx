import type { Route } from '../App'

const LINKS: { route: Route; label: string }[] = [
  { route: 'dashboard', label: 'Dashboard' },
  { route: 'research', label: 'Research' },
  { route: 'room', label: 'Room' },
]

export default function NavBar({ route }: { route: Route }) {
  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#030712]/70 border-b border-zinc-800/40 px-6 py-2">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <a href="#/dashboard" aria-label="VBridge home" className="shrink-0">
          <img
            src="/vbridge-logo.png"
            alt="VBridge — Speak freely, understand deeply"
            className="h-14 w-auto max-w-[180px] object-contain object-left"
          />
        </a>
        <nav className="flex items-center gap-1 text-xs font-semibold uppercase tracking-widest">
          {LINKS.map(link => (
            <a
              key={link.route}
              href={`#/${link.route}`}
              className={`px-3 py-2 rounded-lg transition-colors ${
                route === link.route
                  ? 'text-cyan-400 bg-cyan-500/10'
                  : 'text-zinc-400 hover:text-cyan-400'
              }`}
            >
              {link.label}
            </a>
          ))}
        </nav>
        <a
          href="#/research"
          className="px-4 py-2 text-xs font-bold bg-gradient-to-r from-cyan-500 to-indigo-500 hover:opacity-90 text-white rounded-xl shadow-md shadow-cyan-500/10 active:scale-95 transition-all"
        >
          Launch Research
        </a>
      </div>
    </header>
  )
}
