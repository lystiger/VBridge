import { useEffect, useRef, useState } from 'react'
import {
  API_URL,
  WS_URL,
  LANG_LABEL,
  createRoom,
  joinRoom,
  roomEvent,
  toPcm16,
  uploadTurn,
  type InferenceMode,
  type Lang,
  type RoomAccess,
  type RoomEvent,
} from '../lib/api'

type LogEntry = {
  id: string
  speaker: string
  source_text: string
  translated_text: string
  inference_mode: string
  asr_latency_ms?: number
  mt_latency_ms?: number
}

type RecState = 'idle' | 'recording' | 'sending'

// A single room participant ("one phone"). Open two browser tabs to test both ends.
export default function Room() {
  const [access, setAccess] = useState<RoomAccess | null>(null)
  if (!access) return <Setup onReady={setAccess} />
  return <LiveRoom access={access} onLeave={() => setAccess(null)} />
}

function Setup({ onReady }: { onReady: (a: RoomAccess) => void }) {
  const [tab, setTab] = useState<'create' | 'join'>('create')
  const [name, setName] = useState('Phone A')
  const [source, setSource] = useState<Lang>('vi')
  const [mode, setMode] = useState<InferenceMode>('server')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const target: Lang = source === 'vi' ? 'en' : 'vi'

  async function go() {
    setBusy(true)
    setError('')
    try {
      const access =
        tab === 'create'
          ? await createRoom(name, source, target, mode)
          : await joinRoom(code.trim().toUpperCase(), name, source, target)
      onReady(access)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="max-w-md mx-auto pt-16 pb-24 px-6 relative z-10">
      <h1 className="text-3xl font-black text-white tracking-tight mb-1">Two-Phone Room</h1>
      <p className="text-sm text-zinc-500 mb-6">
        Open this page in two tabs — create in one, join with the code in the other.
      </p>

      <div className="grid grid-cols-2 gap-2 mb-5">
        <TabButton active={tab === 'create'} onClick={() => setTab('create')} label="Create" />
        <TabButton active={tab === 'join'} onClick={() => setTab('join')} label="Join" />
      </div>

      <div className="rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl p-5 space-y-4">
        <Field label="Display name">
          <input
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500/50"
            value={name}
            onChange={e => setName(e.target.value)}
          />
        </Field>

        <Field label="Speaking language">
          <div className="flex items-center gap-2">
            <div className="flex-1 text-center py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm font-bold text-white">
              {LANG_LABEL[source]}
            </div>
            <button
              onClick={() => setSource(target)}
              className="w-9 h-9 rounded-lg bg-zinc-800 border border-zinc-700 text-cyan-400 hover:bg-zinc-700 active:scale-95"
              title="Swap"
            >
              ⇄
            </button>
            <div className="flex-1 text-center py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm font-bold text-cyan-300">
              {LANG_LABEL[target]}
            </div>
          </div>
        </Field>

        {tab === 'create' ? (
          <Field label="Inference mode">
            <div className="grid grid-cols-2 gap-2">
              <ModeButton active={mode === 'server'} onClick={() => setMode('server')} label="Server Host" sub="Scenario 2" />
              <ModeButton active={mode === 'device'} onClick={() => setMode('device')} label="On-Device" sub="Scenario 1" />
            </div>
          </Field>
        ) : (
          <Field label="Room code">
            <input
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm font-mono tracking-widest uppercase text-white focus:outline-none focus:border-cyan-500/50"
              value={code}
              maxLength={6}
              placeholder="ABC234"
              onChange={e => setCode(e.target.value)}
            />
          </Field>
        )}

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <button
          onClick={() => void go()}
          disabled={busy || (tab === 'join' && code.trim().length !== 6)}
          className="w-full py-3 rounded-xl font-bold text-sm bg-gradient-to-r from-cyan-500 to-indigo-500 text-white hover:opacity-90 active:scale-95 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {busy ? 'Connecting…' : tab === 'create' ? 'Create Room' : 'Join Room'}
        </button>
      </div>
    </section>
  )
}

function LiveRoom({ access, onLeave }: { access: RoomAccess; onLeave: () => void }) {
  const ws = useRef<WebSocket | null>(null)
  const seq = useRef(1)
  const audioCtx = useRef<AudioContext | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const pcmChunks = useRef<Int16Array[]>([])
  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const blobChunks = useRef<Blob[]>([])

  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState(access.status)
  const [participantCount, setParticipantCount] = useState(1)
  const [rec, setRec] = useState<RecState>('idle')
  const [log, setLog] = useState<LogEntry[]>([])
  const [error, setError] = useState('')

  const isServer = access.inference_mode === 'server'
  const me = access.participant.participant_id
  const src: Lang = access.participant.source_language
  const tgt: Lang = access.participant.target_language

  useEffect(() => {
    const socket = new WebSocket(`${WS_URL}/ws/rooms/${access.room_id}?token=${access.access_token}`)
    ws.current = socket
    socket.onopen = () => {
      setConnected(true)
      send(roomEvent('participant.ready', access.room_id, me, nextSeq()))
    }
    socket.onclose = () => setConnected(false)
    socket.onerror = () => setError('WebSocket error')
    socket.onmessage = event => {
      const msg = JSON.parse(event.data) as RoomEvent
      if (msg.type === 'room.state') {
        const p = msg.payload as { status?: string; participant_count?: number }
        if (p.status) setStatus(p.status as typeof status)
        if (typeof p.participant_count === 'number') setParticipantCount(p.participant_count)
      } else if (msg.type === 'translation.result') {
        const p = msg.payload as Record<string, unknown>
        setLog(prev => [
          {
            id: msg.event_id,
            speaker: String(p.speaker_id ?? msg.participant_id),
            source_text: String(p.source_text ?? ''),
            translated_text: String(p.translated_text ?? ''),
            inference_mode: String(p.inference_mode ?? '?'),
            asr_latency_ms: typeof p.asr_latency_ms === 'number' ? p.asr_latency_ms : undefined,
            mt_latency_ms: typeof p.mt_latency_ms === 'number' ? p.mt_latency_ms : undefined,
          },
          ...prev,
        ])
      } else if (msg.type === 'error') {
        const p = msg.payload as { code?: string; message?: string }
        setError(`${p.code}: ${p.message}`)
      } else if (msg.type === 'room.closed') {
        setStatus('closed')
      }
    }
    return () => socket.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function nextSeq() {
    const s = seq.current
    seq.current += 1
    return s
  }

  function send(event: RoomEvent) {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(event))
  }

  async function startRecording() {
    setError('')
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.current = media
      if (isServer) {
        const ctx = new AudioContext()
        audioCtx.current = ctx
        pcmChunks.current = []
        const sourceNode = ctx.createMediaStreamSource(media)
        const processor = ctx.createScriptProcessor(4096, 1, 1)
        processor.onaudioprocess = e => {
          const pcm = new Int16Array(toPcm16(e.inputBuffer.getChannelData(0), ctx.sampleRate))
          pcmChunks.current.push(pcm)
        }
        sourceNode.connect(processor)
        processor.connect(ctx.destination)
      } else {
        blobChunks.current = []
        const recorder = new MediaRecorder(media)
        recorder.ondataavailable = e => blobChunks.current.push(e.data)
        recorder.onstop = () => void sendDeviceResult()
        mediaRecorder.current = recorder
        recorder.start()
      }
      setRec('recording')
    } catch {
      setError('Microphone access was denied or is unavailable.')
    }
  }

  async function stopRecording() {
    setRec('sending')
    stream.current?.getTracks().forEach(t => t.stop())
    if (isServer) {
      await audioCtx.current?.close()
      sendServerTurn()
    } else {
      mediaRecorder.current?.stop() // triggers onstop → sendDeviceResult
    }
  }

  // Scenario 2: stream the recorded PCM turn to the host, which runs inference.
  function sendServerTurn() {
    const total = pcmChunks.current.reduce((n, c) => n + c.length, 0)
    if (total === 0) {
      setRec('idle')
      setError('No audio captured.')
      return
    }
    const merged = new Int16Array(total)
    let offset = 0
    for (const c of pcmChunks.current) {
      merged.set(c, offset)
      offset += c.length
    }
    send(
      roomEvent('audio.start', access.room_id, me, nextSeq(), {
        audio_format: 'pcm_s16le',
        sample_rate_hz: 16000,
        channels: 1,
        source_language: src,
        target_language: tgt,
      }),
    )
    ws.current?.send(merged.buffer)
    send(roomEvent('audio.end', access.room_id, me, nextSeq()))
    setRec('idle')
  }

  // Scenario 1: the phone infers locally, then the host only relays the result. Here the
  // browser can't run on-device models, so we produce the result via the server pipeline
  // (clearly a test stand-in) and emit it as a device-produced translation.result.
  async function sendDeviceResult() {
    try {
      const blob = new Blob(blobChunks.current, { type: mediaRecorder.current?.mimeType })
      const result = await uploadTurn(blob, src)
      send(
        roomEvent('translation.result', access.room_id, me, nextSeq(), {
          source_language: result.source_language,
          target_language: result.target_language,
          source_text: result.transcript,
          translated_text: result.translation,
          asr_latency_ms: result.asr_ms,
          mt_latency_ms: result.translation_ms,
          end_to_end_latency_ms: result.total_pipeline_ms,
        }),
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Local inference failed')
    } finally {
      setRec('idle')
    }
  }

  return (
    <section className="max-w-3xl mx-auto pt-12 pb-24 px-6 relative z-10">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight">Room</h1>
          <div className="flex items-center gap-3 mt-1 text-xs">
            <span className="font-mono text-zinc-500">code</span>
            <span className="font-mono text-lg font-bold tracking-widest text-cyan-300">{access.room_code}</span>
            <Badge>{access.inference_mode === 'server' ? 'Server Host' : 'On-Device Relay'}</Badge>
          </div>
        </div>
        <button
          onClick={onLeave}
          className="px-3 py-2 rounded-lg text-xs font-bold bg-zinc-800 border border-zinc-700 text-zinc-300 hover:bg-zinc-700"
        >
          Leave
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-6">
        <Info label="Connection" value={connected ? 'Connected' : 'Offline'} good={connected} />
        <Info label="Status" value={status} />
        <Info label="Participants" value={`${participantCount} / 2`} />
      </div>

      <button
        onMouseDown={() => void startRecording()}
        onMouseUp={() => void stopRecording()}
        onTouchStart={() => void startRecording()}
        onTouchEnd={() => void stopRecording()}
        disabled={!connected || rec === 'sending'}
        className={`w-full py-6 rounded-2xl font-black text-sm tracking-wide transition-all active:scale-[0.98] disabled:opacity-30 disabled:cursor-not-allowed ${
          rec === 'recording'
            ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/20'
            : 'bg-gradient-to-r from-cyan-500 to-indigo-500 text-white shadow-lg shadow-cyan-500/10'
        }`}
      >
        {rec === 'recording' ? '● Release to send' : rec === 'sending' ? 'Sending…' : '🎤 Hold to talk'}
      </button>
      <p className="text-center text-[11px] text-zinc-600 mt-2">
        {isServer
          ? 'Host runs ASR → MT → TTS and broadcasts the result to both phones.'
          : 'This phone produces the result (test stand-in via pipeline); the host only relays it.'}
      </p>

      {error && (
        <div role="alert" className="mt-5 rounded-xl bg-rose-500/10 border border-rose-500/20 p-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      <div className="mt-8 space-y-3">
        <p className="text-[10px] font-mono uppercase font-bold text-zinc-500 tracking-widest">Conversation</p>
        {log.length === 0 && <p className="text-sm text-zinc-600">No turns yet. Hold the button and speak.</p>}
        {log.map(entry => (
          <div key={entry.id} className="rounded-xl bg-zinc-950 border border-zinc-900 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-zinc-500">
                {entry.speaker === me ? 'You' : 'Peer'} · {entry.speaker.slice(0, 8)}
              </span>
              <Badge>{entry.inference_mode}</Badge>
            </div>
            <p className="text-sm text-white font-medium">{entry.source_text}</p>
            <p className="text-sm text-cyan-300 font-medium mt-1">{entry.translated_text}</p>
            {(entry.asr_latency_ms !== undefined || entry.mt_latency_ms !== undefined) && (
              <p className="mt-2 text-[10px] font-mono text-zinc-600">
                {entry.asr_latency_ms !== undefined && `ASR ${entry.asr_latency_ms.toFixed(0)}ms `}
                {entry.mt_latency_ms !== undefined && `· MT ${entry.mt_latency_ms.toFixed(0)}ms`}
              </p>
            )}
          </div>
        ))}
      </div>

      <p className="mt-8 text-[10px] font-mono text-zinc-700 break-all">host: {API_URL}</p>
    </section>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[10px] font-mono uppercase font-bold text-zinc-500 tracking-widest mb-2">{label}</label>
      {children}
    </div>
  )
}

function TabButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`py-2.5 rounded-lg text-xs font-bold border transition-all ${
        active ? 'bg-cyan-500/15 border-cyan-500/50 text-cyan-300' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
      }`}
    >
      {label}
    </button>
  )
}

function ModeButton({ active, onClick, label, sub }: { active: boolean; onClick: () => void; label: string; sub: string }) {
  return (
    <button
      onClick={onClick}
      className={`py-2.5 px-2 rounded-lg border text-center transition-all active:scale-95 ${
        active ? 'bg-cyan-500/15 border-cyan-500/50 text-cyan-300' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
      }`}
    >
      <span className="block text-xs font-bold">{label}</span>
      <span className="block text-[9px] font-mono uppercase tracking-wider opacity-70">{sub}</span>
    </button>
  )
}

function Info({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-xl bg-zinc-900/30 border border-zinc-800/60 p-3">
      <p className="text-[9px] font-mono uppercase font-bold text-zinc-500 tracking-widest">{label}</p>
      <p className={`text-sm font-bold mt-0.5 ${good ? 'text-emerald-400' : 'text-white'}`}>{value}</p>
    </div>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="px-2 py-0.5 rounded-md text-[9px] font-mono uppercase tracking-wider border border-cyan-500/30 bg-cyan-500/5 text-cyan-400">
      {children}
    </span>
  )
}
