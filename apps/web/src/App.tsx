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
      <Backdrop />
      <NavBar route={route} />
      {route === 'research' ? <Research /> : route === 'room' ? <Room /> : <Dashboard />}
    </div>
  )
}
