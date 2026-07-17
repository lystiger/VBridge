import { useRef, useState } from 'react'

type Stage = 'Idle' | 'Listening' | 'Processing' | 'Completed' | 'Error'
type Result = {
  transcript: string; translation: string; source_language: string; target_language: string;
  audio_url: string; asr_ms: number; translation_ms: number; tts_ms: number; total_pipeline_ms: number
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function App() {
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const liveSocket = useRef<WebSocket | null>(null)
  const liveContext = useRef<AudioContext | null>(null)
  const liveStream = useRef<MediaStream | null>(null)
  const [stage, setStage] = useState<Stage>('Idle')
  const [language, setLanguage] = useState<'vi' | 'en'>('vi')
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [liveTranscript, setLiveTranscript] = useState('')
  const [liveTranslation, setLiveTranslation] = useState('')
  const [liveAudioUrl, setLiveAudioUrl] = useState('')

  async function startLive() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const context = new AudioContext(); const source = context.createMediaStreamSource(stream)
      const processor = context.createScriptProcessor(4096, 1, 1)
      const socket = new WebSocket(`${API_URL.replace(/^http/, 'ws')}/pipeline/stream?session_id=${crypto.randomUUID()}&language=${language}`)
      socket.onmessage = event => {
        const message = JSON.parse(event.data) as { type: string; text?: string; audio_url?: string }
        if (message.type === 'turn.detected') setStage('Processing')
        if (message.type === 'asr.partial' || message.type === 'asr.final') setLiveTranscript(message.text ?? '')
        if (message.type === 'translation.partial' || message.type === 'translation.final') setLiveTranslation(message.text ?? '')
        if (message.type === 'turn.completed') { setLiveAudioUrl(message.audio_url ?? ''); setStage('Completed') }
      }
      processor.onaudioprocess = event => {
        if (socket.readyState !== WebSocket.OPEN) return
        const input = event.inputBuffer.getChannelData(0); const ratio = context.sampleRate / 16000
        const pcm = new Int16Array(Math.floor(input.length / ratio))
        for (let i = 0; i < pcm.length; i++) { const value = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)])); pcm[i] = value < 0 ? value * 32768 : value * 32767 }
        socket.send(pcm.buffer)
      }
      source.connect(processor); processor.connect(context.destination)
      liveSocket.current = socket; liveContext.current = context; liveStream.current = stream
      setStage('Listening')
    } catch { setError('Unable to start live microphone streaming.'); setStage('Error') }
  }

  function stopLive() {
    liveSocket.current?.close(); liveStream.current?.getTracks().forEach(track => track.stop())
    void liveContext.current?.close(); setStage('Idle')
  }

  async function startRecording() {
    try {
      setError(''); setResult(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunks.current = []
      recorder.current = new MediaRecorder(stream)
      recorder.current.ondataavailable = event => chunks.current.push(event.data)
      recorder.current.onstop = () => { stream.getTracks().forEach(track => track.stop()); void submit(new Blob(chunks.current, { type: recorder.current?.mimeType })) }
      recorder.current.start(); setStage('Listening')
    } catch { setError('Microphone access was denied or is unavailable.'); setStage('Error') }
  }

  function stopRecording() { recorder.current?.stop(); setStage('Processing') }

  async function submit(audio: Blob) {
    const form = new FormData()
    form.append('audio', audio, 'recording.webm'); form.append('session_id', crypto.randomUUID())
    form.append('speaker', 'speaker_a'); form.append('language', language)
    try {
      const response = await fetch(`${API_URL}/pipeline/upload`, { method: 'POST', body: form })
      if (!response.ok) throw new Error(`Pipeline failed (${response.status})`)
      setResult(await response.json() as Result); setStage('Completed')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Pipeline failed'); setStage('Error') }
  }

  return <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center gap-6 p-6">
    <header><p className="text-sm font-semibold uppercase tracking-[.3em] text-cyan-400">Local meeting translation</p><h1 className="mt-2 text-4xl font-bold">VBridge</h1><p className="mt-2 text-slate-400">Record a turn and run it through the mock ASR → translation → speech pipeline.</p></header>
    <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6 shadow-2xl">
      <div className="flex flex-wrap items-center justify-between gap-4"><div><span className="text-sm text-slate-400">Current stage</span><p className="text-xl font-semibold text-cyan-300">{stage}</p></div><label className="text-sm text-slate-300">Spoken language <select className="ml-2 rounded bg-slate-800 p-2" value={language} onChange={e => setLanguage(e.target.value as 'vi' | 'en')}><option value="vi">Vietnamese</option><option value="en">English</option></select></label></div>
      <div className="mt-6 flex flex-wrap gap-3"><button className="rounded-lg bg-cyan-500 px-5 py-3 font-semibold text-slate-950" disabled={stage === 'Listening' || stage === 'Processing'} onClick={() => void startRecording()}>Record</button><button className="rounded-lg bg-rose-500 px-5 py-3 font-semibold text-white" disabled={stage !== 'Listening'} onClick={stopRecording}>Stop</button><button className="rounded-lg bg-emerald-500 px-5 py-3 font-semibold text-slate-950" disabled={stage === 'Listening' || stage === 'Processing'} onClick={() => void startLive()}>Auto listen</button><button className="rounded-lg bg-slate-700 px-5 py-3 font-semibold" disabled={stage !== 'Listening'} onClick={stopLive}>End live</button></div>
      {error && <p role="alert" className="mt-4 rounded bg-rose-950 p-3 text-rose-200">{error}</p>}
    </section>
    {(liveTranscript || liveTranslation) && <section className="grid gap-4 md:grid-cols-2"><article className="rounded-xl bg-slate-900 p-5"><p className="text-xs uppercase text-slate-500">Live transcript</p><p className="mt-2 text-xl">{liveTranscript}</p></article><article className="rounded-xl bg-slate-900 p-5"><p className="text-xs uppercase text-slate-500">Live translation</p><p className="mt-2 text-xl">{liveTranslation}</p></article>{liveAudioUrl && <audio controls autoPlay className="w-full md:col-span-2" src={`${API_URL}${liveAudioUrl}`} />}</section>}
    {result && <section className="grid gap-4 md:grid-cols-2">
      <article className="rounded-xl bg-slate-900 p-5"><p className="text-xs uppercase text-slate-500">Transcript · {result.source_language}</p><p className="mt-2 text-xl">{result.transcript}</p></article>
      <article className="rounded-xl bg-slate-900 p-5"><p className="text-xs uppercase text-slate-500">Translation · {result.target_language}</p><p className="mt-2 text-xl">{result.translation}</p></article>
      <article className="rounded-xl bg-slate-900 p-5 md:col-span-2"><audio controls className="w-full" src={`${API_URL}${result.audio_url}`} /><div className="mt-4 grid grid-cols-2 gap-2 text-sm text-slate-400 md:grid-cols-4"><span>ASR {result.asr_ms.toFixed(1)} ms</span><span>Translation {result.translation_ms.toFixed(1)} ms</span><span>TTS {result.tts_ms.toFixed(1)} ms</span><span>Total {result.total_pipeline_ms.toFixed(1)} ms</span></div></article>
    </section>}
  </main>
}
