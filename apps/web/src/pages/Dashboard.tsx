// Team-intro dashboard. Presents the SilentVoix team, the VBridge hybrid
// architecture, and the two demonstration scenarios that prove it out.

type Member = { name: string; role: string; focus: string; accent: string }

// NOTE: fill in real names/handles per teammate. Roles are fixed by the brief.
const TEAM: Member[] = [
  {
    name: 'AI Engineer',
    role: 'Models & Translation Quality',
    focus: 'ASR/MT model selection, translation quality, turn-taking.',
    accent: 'from-cyan-400 to-teal-300',
  },
  {
    name: 'MLOps Engineer',
    role: 'Serving, Latency & Demo',
    focus: 'Serving, latency budget, infra, the host server, UX.',
    accent: 'from-teal-300 to-indigo-400',
  },
  {
    name: 'Data Engineer',
    role: 'Glossary, Eval & Pitch',
    focus: 'Glossary, test dialogues, evaluation harness, pitch.',
    accent: 'from-indigo-400 to-fuchsia-400',
  },
]

const SCENARIOS = [
  {
    tag: 'Scenario 1',
    title: 'Offline · On-Device Relay',
    body: 'Two phones run the AI pipeline on-device. The host is a pure relay — no network dependency, full privacy. This is the reliability floor.',
    badge: 'inference_mode: device',
    accent: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5',
  },
  {
    tag: 'Scenario 2',
    title: 'Online · Host + Inference',
    body: 'The host runs the full ASR → MT → TTS pipeline; phones are thin clients. Heavier models, higher quality when a host is available.',
    badge: 'inference_mode: server',
    accent: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/5',
  },
]

export default function Dashboard() {
  return (
    <>
      <section className="max-w-5xl mx-auto pt-24 pb-12 px-6 text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900/80 border border-zinc-800 backdrop-blur-md text-[11px] font-medium text-zinc-400 mb-6 shadow-inner">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          Team SilentVoix · VAIC 2026
        </div>
        <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-[1.1] mb-6">
          Real-Time Meeting <br />
          <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-indigo-400 bg-clip-text text-transparent">
            AI Translation
          </span>
        </h1>
        <p className="text-sm md:text-base text-zinc-400 max-w-xl mx-auto mb-8 leading-relaxed">
          A hybrid Vietnamese ↔ English interpreter: it keeps working offline with
          on-device inference, and gets sharper when a host server is available.
        </p>
        <div className="flex items-center justify-center gap-3">
          <a
            href="#/research"
            className="px-5 py-2.5 text-xs font-bold bg-gradient-to-r from-cyan-500 to-indigo-500 hover:opacity-90 text-white rounded-xl shadow-md shadow-cyan-500/10 active:scale-95 transition-all"
          >
            Open Research Console
          </a>
          <a
            href="#architecture"
            className="px-5 py-2.5 text-xs font-bold bg-zinc-900/60 border border-zinc-800 text-zinc-300 rounded-xl hover:border-cyan-500/40 transition-all"
          >
            The Hybrid Approach
          </a>
        </div>
      </section>

      {/* Headline metrics */}
      <section className="max-w-5xl mx-auto pb-12 px-6 relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <Stat value="0.22s" label="Ultra-Low Latency" accent="from-cyan-400 to-teal-300"
            note="Measured end-to-end audio processing, shown the moment a turn ends." />
          <Stat value="81.2%" label="SOTA Accuracy" accent="from-teal-300 to-indigo-400"
            note="Real EN → VI evaluation across complex sentence structures." />
          <Stat value="2 Modes" label="Hybrid by Design" accent="from-indigo-400 to-fuchsia-400"
            note="On-device offline relay and full server-hosted inference, one contract." />
        </div>
      </section>

      {/* Hybrid architecture / scenarios */}
      <section id="architecture" className="max-w-5xl mx-auto pb-12 px-6 relative z-10 scroll-mt-24">
        <h2 className="text-2xl font-bold text-white tracking-tight mb-2">The Hybrid Approach</h2>
        <p className="text-sm text-zinc-500 mb-6 max-w-2xl">
          One system, one result contract, proven two ways. The same two phones and the
          same conversation UI can demonstrate both scenarios back-to-back.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {SCENARIOS.map(s => (
            <div
              key={s.tag}
              className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl hover:border-cyan-500/30 transition-all"
            >
              <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider border mb-3 ${s.accent}`}>
                {s.tag}
              </span>
              <h3 className="text-lg font-bold text-white tracking-tight mb-2">{s.title}</h3>
              <p className="text-xs text-zinc-400 leading-relaxed mb-4">{s.body}</p>
              <code className="text-[10px] font-mono text-zinc-500">{s.badge}</code>
            </div>
          ))}
        </div>
      </section>

      {/* Team */}
      <section id="team" className="max-w-5xl mx-auto pb-24 px-6 relative z-10 scroll-mt-24">
        <h2 className="text-2xl font-bold text-white tracking-tight mb-2">The Team</h2>
        <p className="text-sm text-zinc-500 mb-6">Three engineers, one 48-hour build.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {TEAM.map(m => (
            <div
              key={m.role}
              className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl hover:border-indigo-500/30 transition-all"
            >
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-tr ${m.accent} flex items-center justify-center mb-4 shadow-lg`}>
                <span className="text-zinc-950 font-black text-lg">{m.name.charAt(0)}</span>
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">{m.name}</h3>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-cyan-400 mt-0.5 mb-3">{m.role}</p>
              <p className="text-xs text-zinc-500 leading-relaxed">{m.focus}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="max-w-5xl mx-auto py-8 px-6 border-t border-zinc-900/80 text-center text-[10px] font-mono text-zinc-600">
        <p>© 2026 VBridge · Team SilentVoix · Vietnam AI Innovation Challenge.</p>
      </footer>
    </>
  )
}

function Stat({ value, label, note, accent }: { value: string; label: string; note: string; accent: string }) {
  return (
    <div className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl hover:border-cyan-500/40 transition-all">
      <div className={`text-4xl font-black tracking-tight mb-1 bg-gradient-to-r ${accent} bg-clip-text text-transparent`}>{value}</div>
      <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-2">{label}</p>
      <p className="text-zinc-500 text-xs leading-relaxed">{note}</p>
    </div>
  )
}
