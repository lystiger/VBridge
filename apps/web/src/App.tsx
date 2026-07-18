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

      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293710_1px,transparent_1px),linear-gradient(to_bottom,#1f293710_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />
      <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-[30%] right-[-10%] w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-[160px] pointer-events-none" />

      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#030712]/70 border-b border-zinc-800/40 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5 cursor-pointer group">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-cyan-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <span className="text-white font-black text-xs">V</span>
            </div>
            <span className="text-xl font-black tracking-wider bg-gradient-to-r from-cyan-400 via-teal-300 to-indigo-400 bg-clip-text text-transparent">
              VBRIDGE
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-xs font-semibold uppercase tracking-widest text-zinc-400">
            <a href="#features" className="hover:text-cyan-400 transition-colors">Features</a>
            <a href="#workspace" className="hover:text-cyan-400 transition-colors">Live Workspace</a>
            <a href="#docs" className="hover:text-cyan-400 transition-colors">Architecture</a>
          </nav>
          <a href="#workspace" className="px-4 py-2 text-xs font-bold bg-gradient-to-r from-cyan-500 to-indigo-500 hover:opacity-90 text-white rounded-xl shadow-md shadow-cyan-500/10 active:scale-95 transition-all">
            Launch App
          </a>
        </div>
      </header>

      <section className="max-w-5xl mx-auto pt-24 pb-16 px-6 text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900/80 border border-zinc-800 backdrop-blur-md text-[11px] font-medium text-zinc-400 mb-6 shadow-inner">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" /> 
          Next-Generation Real-Time AI Pipeline
        </div>
        <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-[1.1] mb-6">
          Real-Time Meeting <br />
          <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-indigo-400 bg-clip-text text-transparent">
            AI Translation
          </span>
        </h1>
        <p className="text-sm md:text-base text-zinc-400 max-w-xl mx-auto mb-8 leading-relaxed">
          Xóa bỏ rào cản ngôn ngữ tức thì. Hệ thống tối ưu hóa qua ONNX Runtime đạt độ trễ siêu thấp phục vụ các tập đoàn toàn cầu.
        </p>
      </section>

      <section id="features" className="max-w-5xl mx-auto pb-16 px-6 relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl relative group hover:border-cyan-500/40 transition-all duration-300">
            <div className="text-4xl font-black text-white tracking-tight mb-1 bg-gradient-to-r from-cyan-400 to-teal-300 bg-clip-text text-transparent">0.22s</div>
            <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-2">Ultra-Low Latency</p>
            <p className="text-zinc-500 text-xs leading-relaxed">Độ trễ xử lý âm thanh thực tế đạt mốc kỷ lục, hiển thị bản dịch ngay khi dứt câu.</p>
          </div>
          <div className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl relative group hover:border-teal-400/40 transition-all duration-300">
            <div className="text-4xl font-black text-white tracking-tight mb-1 bg-gradient-to-r from-teal-300 to-indigo-400 bg-clip-text text-transparent">81.2%</div>
            <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-2">SOTA Accuracy</p>
            <p className="text-zinc-500 text-xs leading-relaxed">Độ chính xác vượt trội đo đạc thực tế qua bộ kiểm thử cấu trúc câu phức tạp EN ➔ VI.</p>
          </div>
          <div className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 backdrop-blur-xl relative group hover:border-indigo-500/40 transition-all duration-300 flex flex-col justify-between">
            <div>
              <div className="text-xl font-bold text-white tracking-tight mb-1 flex items-center gap-2">
                <span className="text-indigo-400">🛡️</span> On-Premise
              </div>
              <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">Enterprise Grade</p>
            </div>
            <p className="text-zinc-500 text-xs leading-relaxed">Mô hình nén gọn tối đa, sẵn sàng triển khai nội bộ bảo mật tuyệt đối cho doanh nghiệp.</p>
          </div>
        </div>
      </section>

      <section id="workspace" className="max-w-4xl mx-auto pb-24 px-6 relative z-10 scroll-mt-24">
        <div className="rounded-2xl bg-[#090d1a]/90 border border-zinc-800/80 p-6 md:p-8 shadow-2xl relative backdrop-blur-2xl">
          <div className="absolute top-0 left-10 right-10 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />
          
          <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/60">
            <div>
              <div className="flex items-center gap-2 text-[10px] font-mono tracking-widest text-cyan-400 uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                VBridge Live Terminal Workspace
              </div>
              <h2 className="text-xl font-bold text-white tracking-tight mt-1">Interactive Audio Pipeline</h2>
            </div>

            <div className="flex items-center gap-2 bg-zinc-950 px-3 py-2 rounded-xl border border-zinc-800 text-xs">
              <span className="text-zinc-500 font-medium">Target:</span>
              <select 
                className="bg-transparent font-bold text-white focus:outline-none cursor-pointer"
                value={language} 
                onChange={e => setLanguage(e.target.value as 'vi' | 'en')}
              >
                <option value="vi" className="bg-zinc-950 text-white">Vietnamese (vi)</option>
                <option value="en" className="bg-zinc-950 text-white">English (en)</option>
              </select>
            </div>
          </div>

          <div className="bg-zinc-950/60 rounded-xl p-4 border border-zinc-900/80 flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-500">Status:</span>
              <span className={`px-2.5 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-wider border ${
                stage === 'Idle' ? 'bg-zinc-900/60 text-zinc-400 border-zinc-800' :
                stage === 'Listening' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' :
                stage === 'Processing' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse' :
                stage === 'Completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                'bg-rose-500/10 text-rose-400 border-rose-500/30'
              }`}>
                {stage}
              </span>
            </div>

            {stage === 'Listening' ? (
              <div className="flex items-center gap-0.5 h-4 px-2">
                <div className="w-0.5 bg-cyan-400 rounded-full wv-1 h-full" />
                <div className="w-0.5 bg-cyan-400 rounded-full wv-2 h-full" />
                <div className="w-0.5 bg-cyan-400 rounded-full wv-3 h-full" />
                <div className="w-0.5 bg-cyan-400 rounded-full wv-4 h-full" />
                <div className="w-0.5 bg-cyan-400 rounded-full wv-5 h-full" />
              </div>
            ) : (
              <span className="text-[10px] text-zinc-600 font-mono">SYS_READY</span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <button 
              className="py-3 px-4 rounded-xl font-bold text-xs bg-cyan-500 text-zinc-950 hover:bg-cyan-400 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95 shadow-lg shadow-cyan-500/10"
              disabled={stage === 'Listening' || stage === 'Processing'} 
              onClick={() => void startRecording()}
            >
              🎤 Record Turn
            </button>
            <button 
              className="py-3 px-4 rounded-xl font-bold text-xs bg-zinc-800 text-rose-400 border border-zinc-700/60 hover:bg-zinc-700 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95"
              disabled={stage !== 'Listening'} 
              onClick={stopRecording}
            >
              ⏹️ Stop
            </button>
            <button 
              className="py-3 px-4 rounded-xl font-bold text-xs bg-gradient-to-r from-emerald-500 to-teal-500 text-zinc-950 hover:opacity-90 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95 shadow-lg shadow-emerald-500/10"
              disabled={stage === 'Listening' || stage === 'Processing'} 
              onClick={() => void startLive()}
            >
              📡 Auto Listen
            </button>
            <button 
              className="py-3 px-4 rounded-xl font-bold text-xs bg-zinc-800 text-zinc-400 border border-zinc-700/60 hover:bg-zinc-700 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-95"
              disabled={stage !== 'Listening'} 
              onClick={stopLive}
            >
              ❌ End Live
            </button>
          </div>

          {error && (
            <div role="alert" className="mb-6 rounded-xl bg-rose-500/10 border border-rose-500/20 p-4 text-xs text-rose-300 flex items-center gap-2">
              <span>⚠️</span> {error}
            </div>
          )}

          {(liveTranscript || liveTranslation) && (
            <div className="mt-6 grid gap-4 md:grid-cols-2 pt-6 border-t border-zinc-800/40">
              <div className="rounded-xl bg-zinc-950/80 p-4 border border-zinc-900">
                <p className="text-[10px] font-mono uppercase font-bold text-zinc-500 tracking-wider">Live Transcript Stream</p>
                <p className="mt-2 text-sm text-zinc-100 font-medium">{liveTranscript || 'Chờ âm thanh từ micro...'}</p>
              </div>
              <div className="rounded-xl bg-zinc-950/80 p-4 border border-zinc-900 relative">
                <div className="absolute top-3 right-3 w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <p className="text-[10px] font-mono uppercase font-bold text-cyan-400 tracking-wider">AI Live Translation</p>
                <p className="mt-2 text-sm text-cyan-100 font-medium">{liveTranslation || 'Đang biên dịch trực tiếp...'}</p>
              </div>
              {liveAudioUrl && (
                <div className="md:col-span-2 bg-zinc-950/40 p-4 rounded-xl border border-zinc-900 flex flex-col gap-2">
                  <p className="text-[10px] text-zinc-400 font-mono uppercase font-bold">Generated Pipeline Audio Output</p>
                  <audio controls autoPlay className="w-full h-9 accent-cyan-500" src={`${API_URL}${liveAudioUrl}`} />
                </div>
              )}
            </div>
          )}

          {result && (
            <div className="mt-6 grid gap-4 md:grid-cols-2 pt-6 border-t border-zinc-800/40">
              <div className="rounded-xl bg-zinc-950 p-4 border border-zinc-900">
                <p className="text-[10px] font-mono uppercase font-bold text-zinc-500 tracking-wider">Source Text ({result.source_language})</p>
                <p className="mt-2 text-sm text-white font-medium leading-relaxed">{result.transcript}</p>
              </div>
              <div className="rounded-xl bg-zinc-950 p-4 border border-zinc-900 border-l-cyan-500/40">
                <p className="text-[10px] font-mono uppercase font-bold text-cyan-400 tracking-wider">Translated Text ({result.target_language})</p>
                <p className="mt-2 text-sm text-cyan-200 font-medium leading-relaxed">{result.translation}</p>
              </div>
              <div className="rounded-xl bg-zinc-950 p-4 md:col-span-2 border border-zinc-900">
                <p className="text-[10px] text-zinc-400 font-mono uppercase font-bold mb-2">TTS Speech Synthesis Output</p>
                <audio controls className="w-full h-9 accent-cyan-500 mb-4" src={`${API_URL}${result.audio_url}`} />
                
                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-zinc-500 md:grid-cols-4 pt-3 border-t border-zinc-900">
                  <div className="bg-zinc-900/40 px-2.5 py-1.5 rounded border border-zinc-800/60">ASR Latency: <span className="text-white font-bold">{result.asr_ms.toFixed(1)}ms</span></div>
                  <div className="bg-zinc-900/40 px-2.5 py-1.5 rounded border border-zinc-800/60">MT Latency: <span className="text-white font-bold">{result.translation_ms.toFixed(1)}ms</span></div>
                  <div className="bg-zinc-900/40 px-2.5 py-1.5 rounded border border-zinc-800/60">TTS Latency: <span className="text-white font-bold">{result.tts_ms.toFixed(1)}ms</span></div>
                  <div className="bg-gradient-to-r from-cyan-950/50 to-indigo-950/50 text-cyan-400 border border-cyan-900/60 px-2.5 py-1.5 rounded font-bold">Total Hub: {result.total_pipeline_ms.toFixed(1)}ms</div>
                </div>
              </div>
            </div>
          )}

        </div>
      </section>

      <footer className="max-w-5xl mx-auto py-8 px-6 mt-12 border-t border-zinc-900/80 text-center text-[10px] font-mono text-zinc-600">
        <p>© 2026 VBridge AI Corp. Built with ONNX Pipeline Runtime Optimization. All rights reserved.</p>
      </footer>
    </div>
  )
}