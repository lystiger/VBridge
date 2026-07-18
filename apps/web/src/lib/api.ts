export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const WS_URL = API_URL.replace(/^http/, 'ws')

export type Lang = 'vi' | 'en'

// Which side runs the AI pipeline.
//  - 'server'  → Scenario 2: this host runs ASR → MT → TTS (thin-client phones).
//  - 'device'  → Scenario 1: phones self-infer on-device; the host only relays results.
export type InferenceMode = 'server' | 'device'

export type PipelineResult = {
  transcript: string
  translation: string
  source_language: string
  target_language: string
  audio_url: string
  asr_ms: number
  translation_ms: number
  tts_ms: number
  total_pipeline_ms: number
}

export const LANG_LABEL: Record<Lang, string> = {
  vi: 'Vietnamese',
  en: 'English',
}

export type RoomAccess = {
  room_id: string
  room_code: string
  status: string
  inference_mode: InferenceMode
  participant: { participant_id: string; display_name: string; is_owner: boolean }
  access_token: string
  expires_at: string
}

// Create a room, choosing which side runs inference (Scenario 1 vs 2).
export async function createRoom(
  displayName: string,
  source: Lang,
  target: Lang,
  inferenceMode: InferenceMode,
): Promise<RoomAccess> {
  const res = await fetch(`${API_URL}/rooms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      display_name: displayName,
      source_language: source,
      target_language: target,
      inference_mode: inferenceMode,
    }),
  })
  if (!res.ok) throw new Error(`Room creation failed (${res.status})`)
  return (await res.json()) as RoomAccess
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { method: 'GET' })
    return res.ok
  } catch {
    return false
  }
}

export async function uploadTurn(
  audio: Blob,
  language: Lang,
  sessionId = crypto.randomUUID(),
): Promise<PipelineResult> {
  const form = new FormData()
  form.append('audio', audio, 'recording.webm')
  form.append('session_id', sessionId)
  form.append('speaker', 'speaker_a')
  form.append('language', language)
  const res = await fetch(`${API_URL}/pipeline/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Pipeline failed (${res.status})`)
  return (await res.json()) as PipelineResult
}
