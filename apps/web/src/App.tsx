import { useEffect, useState } from 'react'
import Backdrop from './components/Backdrop'
import NavBar from './components/NavBar'
import Dashboard from './pages/Dashboard'
import Research from './pages/Research'
import Room from './pages/Room'

export type Route = 'dashboard' | 'research' | 'room'

function parseHash(): Route {
  const hash = window.location.hash.replace(/^#\/?/, '')
  if (hash === 'research') return 'research'
  if (hash === 'room') return 'room'
  return 'dashboard'
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseHash)

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <div className="min-h-screen bg-[#030712] text-zinc-100 font-sans relative overflow-x-hidden selection:bg-cyan-500/30">
      <style>{`
        @keyframes wave-bounce { 0%, 100% { transform: scaleY(0.3); } 50% { transform: scaleY(1); } }
        .wv-1 { animation: wave-bounce 0.6s ease-in-out infinite; }
        .wv-2 { animation: wave-bounce 0.4s ease-in-out infinite 0.1s; }
        .wv-3 { animation: wave-bounce 0.8s ease-in-out infinite 0.2s; }
        .wv-4 { animation: wave-bounce 0.5s ease-in-out infinite 0.3s; }
        .wv-5 { animation: wave-bounce 0.7s ease-in-out infinite 0.4s; }
      `}</style>

      <Backdrop />
      <NavBar route={route} />
      {route === 'research' ? <Research /> : route === 'room' ? <Room /> : <Dashboard />}
    </div>
  )
}
