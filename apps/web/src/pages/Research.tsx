import { useEffect, useRef, useState } from 'react'
import {
  API_URL,
  WS_URL,
  LANG_LABEL,
  checkHealth,
  uploadTurn,
  type InferenceMode,
  type Lang,
  type PipelineResult,
} from '../lib/api'

type Stage = 'Idle' | 'Listening' | 'Processing' | 'Completed' | 'Error'

export default function Research() {
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const liveSocket = useRef<WebSocket | null>(null)
  const liveContext = useRef<AudioContext | null>(null)
  const liveStream = useRef<MediaStream | null>(null)

  const [mode, setMode] = useState<InferenceMode>('server')
  const [source, setSource] = useState<Lang>('vi')
  const target: Lang = source === 'vi' ? 'en' : 'vi'

  const [stage, setStage] = useState<Stage>('Idle')
  const [online, setOnline] = useState<boolean | null>(null)
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [error, setError] = useState('')
  const [liveTranscript, setLiveTranscript] = useState('')
  const [liveTranslation, setLiveTranslation] = useState('')
  const [liveAudioUrl, setLiveAudioUrl] = useState('')

  const busy = stage === 'Listening' || stage === 'Processing'
  const serverMode = mode === 'server'

  useEffect(() => {
    let alive = true
    const ping = () => checkHealth().then(ok => alive && setOnline(ok))
    ping()
    const id = setInterval(ping, 10_000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  function reset() {
    setError('')
    setResult(null)
    setLiveTranscript('')
    setLiveTranslation('')
    setLiveAudioUrl('')
  }

  async function startLive() {
    reset()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const context = new AudioContext()
      const src = context.createMediaStreamSource(stream)
      const processor = context.createScriptProcessor(4096, 1, 1)
      const socket = new WebSocket(
        `${WS_URL}/pipeline/stream?session_id=${crypto.randomUUID()}&language=${source}`,
      )
      socket.onmessage = event => {
        const message = JSON.parse(event.data) as { type: string; text?: string; audio_url?: string }
        if (message.type === 'turn.detected') setStage('Processing')
        if (message.type === 'asr.partial' || message.type === 'asr.final') setLiveTranscript(message.text ?? '')
        if (message.type === 'translation.partial' || message.type === 'translation.final')
          setLiveTranslation(message.text ?? '')
        if (message.type === 'turn.completed') {
          setLiveAudioUrl(message.audio_url ?? '')
          setStage('Completed')
        }
      }
      processor.onaudioprocess = event => {
        if (socket.readyState !== WebSocket.OPEN) return
        const input = event.inputBuffer.getChannelData(0)
        const ratio = context.sampleRate / 16000
        const pcm = new Int16Array(Math.floor(input.length / ratio))
        for (let i = 0; i < pcm.length; i++) {
          const value = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)]))
          pcm[i] = value < 0 ? value * 32768 : value * 32767
        }
        socket.send(pcm.buffer)
      }
      src.connect(processor)
      processor.connect(context.destination)
      liveSocket.current = socket
      liveContext.current = context
      liveStream.current = stream
      setStage('Listening')
    } catch {
      setError('Unable to start live microphone streaming.')
      setStage('Error')
    }
  }

  function stopLive() {
    liveSocket.current?.close()
    liveStream.current?.getTracks().forEach(track => track.stop())
    void liveContext.current?.close()
    setStage('Idle')
  }

  async function startRecording() {
    reset()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunks.current = []
      recorder.current = new MediaRecorder(stream)
      recorder.current.ondataavailable = event => chunks.current.push(event.data)
      recorder.current.onstop = () => {
        stream.getTracks().forEach(track => track.stop())
        void submit(new Blob(chunks.current, { type: recorder.current?.mimeType }))
      }
      recorder.current.start()
      setStage('Listening')
    } catch {
      setError('Microphone access was denied or is unavailable.')
      setStage('Error')
    }
  }

  function stopRecording() {
    recorder.current?.stop()
    setStage('Processing')
  }

  async function submit(audio: Blob) {
    try {
      setResult(await uploadTurn(audio, source))
      setStage('Completed')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Pipeline failed')
      setStage('Error')
    }
  }

  return (
    <section className="max-w-6xl mx-auto pt-12 pb-24 px-6 relative z-10">
      <div className="mb-8">
        <div className="text-[10px] font-mono tracking-widest text-cyan-400 uppercase">
          VBridge Research Console
        </div>
        <h1 className="text-3xl font-black text-white tracking-tight mt-1">Pipeline Playground</h1>
        <p className="text-sm text-zinc-500 mt-1 max-w-2xl">
          Drive the ASR → MT → TTS pipeline, switch inference modes, and read real per-stage latency.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
        {/* Settings sidebar */}
        <aside className="space-y-5 lg:sticky lg:top-24 self-start">
          <Panel title="Inference Mode">
            <div className="grid grid-cols-2 gap-2">
              <ModeButton
                active={serverMode}
                onClick={() => setMode('server')}
                label="Server Host"
                sub="Scenario 2"
              />
              <ModeButton
                active={!serverMode}
                onClick={() => setMode('device')}
                label="On-Device"
                sub="Scenario 1"
              />
            </div>
            <p className="mt-3 text-[11px] text-zinc-500 leading-relaxed">
              {serverMode
                ? 'This host runs the full pipeline. Phones are thin clients.'
                : 'Phones self-infer offline; the host only relays results.'}
            </p>
          </Panel>

          <Panel title="Direction">
            <div className="flex items-center justify-between gap-2">
              <div className="flex-1 text-center py-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-sm font-bold text-white">
                {LANG_LABEL[source]}
              </div>
              <button
                onClick={() => setSource(target)}
                disabled={busy}
                className="shrink-0 h-9 rounded-lg bg-zinc-800 border border-zinc-700 px-3 text-[10px] font-bold uppercase tracking-wider text-cyan-400 hover:bg-zinc-700 active:scale-95 transition-all disabled:opacity-30"
              >
                Swap
              </button>
              <div className="flex-1 text-center py-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-sm font-bold text-cyan-300">
                {LANG_LABEL[target]}
              </div>
            </div>
            <p className="mt-3 text-[11px] text-zinc-500">Speaking in {LANG_LABEL[source]}.</p>
          </Panel>

          <Panel title="Host">
            <div className="text-xs">
              <span className="text-zinc-400 font-medium">
                {online === null ? 'Checking…' : online ? 'Connected' : 'Offline'}
              </span>
            </div>
            <p className="mt-2 text-[10px] font-mono text-zinc-600 break-all">{API_URL}</p>
          </Panel>
        </aside>

        {/* Working area */}
        <div className="rounded-2xl bg-[#090d1a]/90 border border-zinc-800/80 p-6 md:p-8 shadow-2xl relative backdrop-blur-2xl">
          <div className="absolute top-0 left-10 right-10 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />

          <div className="bg-zinc-950/60 rounded-xl p-4 border border-zinc-900/80 flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-500">Status:</span>
              <span
                className={`px-2.5 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider border ${
                  stage === 'Idle'
                    ? 'bg-zinc-900/60 text-zinc-400 border-zinc-800'
                    : stage === 'Listening'
                      ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                      : stage === 'Processing'
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse'
                        : stage === 'Completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                }`}
              >
                {stage}
              </span>
            </div>
            <span className="text-[10px] text-zinc-600 font-mono">
              {stage === 'Listening' ? 'CAPTURING_AUDIO' : 'SYS_READY'}
            </span>
          </div>

          {serverMode ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
              <button
                className="py-3 px-4 rounded-xl font-bold text-xs bg-cyan-500 text-zinc-950 hover:bg-cyan-400 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95 shadow-lg shadow-cyan-500/10"
                disabled={busy}
                onClick={() => void startRecording()}
              >
                Record Turn
              </button>
              <button
                className="py-3 px-4 rounded-xl font-bold text-xs bg-zinc-800 text-rose-400 border border-zinc-700/60 hover:bg-zinc-700 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95"
                disabled={stage !== 'Listening'}
                onClick={stopRecording}
              >
                Stop
              </button>
              <button
                className="py-3 px-4 rounded-xl font-bold text-xs bg-gradient-to-r from-emerald-500 to-teal-500 text-zinc-950 hover:opacity-90 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95 shadow-lg shadow-emerald-500/10"
                disabled={busy}
                onClick={() => void startLive()}
              >
                Auto Listen
              </button>
              <button
                className="py-3 px-4 rounded-xl font-bold text-xs bg-zinc-800 text-zinc-400 border border-zinc-700/60 hover:bg-zinc-700 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95"
                disabled={stage !== 'Listening'}
                onClick={stopLive}
              >
                End Live
              </button>
            </div>
          ) : (
            <div className="mb-6 rounded-xl bg-emerald-500/5 border border-emerald-500/20 p-5 text-xs text-emerald-200/80 leading-relaxed">
              <p className="font-bold text-emerald-300 mb-1">On-device relay mode</p>
              In this scenario the paired phones run inference locally and the host only relays the
              finished <code className="font-mono">translation.result</code> between them. Use the
              two-phone room flow to exercise it — the server does not transcribe here.
            </div>
          )}

          {error && (
            <div role="alert" className="mb-6 rounded-xl bg-rose-500/10 border border-rose-500/20 p-4 text-xs text-rose-300">
              {error}
            </div>
          )}

          {(liveTranscript || liveTranslation) && (
            <div className="grid gap-4 md:grid-cols-2 pt-2">
              <OutputCard label="Live Transcript Stream" text={liveTranscript || 'Waiting for audio…'} />
              <OutputCard label="AI Live Translation" text={liveTranslation || 'Translating…'} accent />
              {liveAudioUrl && (
                <AudioOut label="Generated Pipeline Audio" src={`${API_URL}${liveAudioUrl}`} autoPlay />
              )}
            </div>
          )}

          {result && (
            <div className="grid gap-4 md:grid-cols-2 pt-2">
              <OutputCard label={`Source (${result.source_language})`} text={result.transcript} />
              <OutputCard label={`Translation (${result.target_language})`} text={result.translation} accent />
              <div className="rounded-xl bg-zinc-950 p-4 md:col-span-2 border border-zinc-900">
                <p className="text-[10px] text-zinc-400 font-mono uppercase font-bold mb-2">TTS Speech Output</p>
                <audio controls className="w-full h-9 accent-cyan-500 mb-4" src={`${API_URL}${result.audio_url}`} />
                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-zinc-500 md:grid-cols-4 pt-3 border-t border-zinc-900">
                  <Metric label="ASR" value={result.asr_ms} />
                  <Metric label="MT" value={result.translation_ms} />
                  <Metric label="TTS" value={result.tts_ms} />
                  <div className="bg-gradient-to-r from-cyan-950/50 to-indigo-950/50 text-cyan-400 border border-cyan-900/60 px-2.5 py-1.5 rounded font-bold">
                    Total: {result.total_pipeline_ms.toFixed(1)}ms
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl p-5">
      <p className="text-[10px] font-mono uppercase font-bold text-zinc-500 tracking-widest mb-3">{title}</p>
      {children}
    </div>
  )
}

function ModeButton({ active, onClick, label, sub }: { active: boolean; onClick: () => void; label: string; sub: string }) {
  return (
    <button
      onClick={onClick}
      className={`py-2.5 px-2 rounded-lg border text-center transition-all active:scale-95 ${
        active
          ? 'bg-cyan-500/15 border-cyan-500/50 text-cyan-300'
          : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
      }`}
    >
      <span className="block text-xs font-bold">{label}</span>
      <span className="block text-[9px] font-mono uppercase tracking-wider opacity-70">{sub}</span>
    </button>
  )
}

function OutputCard({ label, text, accent }: { label: string; text: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl bg-zinc-950 p-4 border border-zinc-900 ${accent ? 'border-l-cyan-500/40' : ''}`}>
      <p className={`text-[10px] font-mono uppercase font-bold tracking-wider ${accent ? 'text-cyan-400' : 'text-zinc-500'}`}>
        {label}
      </p>
      <p className={`mt-2 text-sm font-medium leading-relaxed ${accent ? 'text-cyan-200' : 'text-white'}`}>{text}</p>
    </div>
  )
}

function AudioOut({ label, src, autoPlay }: { label: string; src: string; autoPlay?: boolean }) {
  return (
    <div className="md:col-span-2 bg-zinc-950/40 p-4 rounded-xl border border-zinc-900 flex flex-col gap-2">
      <p className="text-[10px] text-zinc-400 font-mono uppercase font-bold">{label}</p>
      <audio controls autoPlay={autoPlay} className="w-full h-9 accent-cyan-500" src={src} />
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-zinc-900/40 px-2.5 py-1.5 rounded border border-zinc-800/60">
      {label} Latency: <span className="text-white font-bold">{value.toFixed(1)}ms</span>
    </div>
  )
}
