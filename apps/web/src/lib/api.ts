import { z } from 'zod'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const WS_URL = API_URL.replace(/^http/, 'ws')
export const PROTOCOL_VERSION = '1.0.0' as const

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

const langSchema = z.enum(['vi', 'en'])
const inferenceModeSchema = z.enum(['server', 'device'])
const roomAccessSchema = z.object({
  protocol_version: z.literal(PROTOCOL_VERSION),
  room_id: z.string().min(1),
  room_code: z.string().length(6),
  status: z.string(),
  inference_mode: inferenceModeSchema,
  participant: z.object({
    participant_id: z.string().min(1),
    display_name: z.string(),
    source_language: langSchema,
    target_language: langSchema,
    connected: z.boolean(),
    is_owner: z.boolean(),
  }),
  access_token: z.string().min(1),
  expires_at: z.string(),
})

export type RoomAccess = z.infer<typeof roomAccessSchema>

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
  return roomAccessSchema.parse(await res.json())
}

export async function joinRoom(
  roomCode: string,
  displayName: string,
  source: Lang,
  target: Lang,
): Promise<RoomAccess> {
  const res = await fetch(`${API_URL}/rooms/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      room_code: roomCode,
      display_name: displayName,
      source_language: source,
      target_language: target,
    }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail?.code ?? `Join failed (${res.status})`)
  }
  return roomAccessSchema.parse(await res.json())
}

const roomEventSchema = z.object({
  protocol_version: z.literal(PROTOCOL_VERSION),
  type: z.string().min(1),
  event_id: z.string().min(1),
  room_id: z.string().min(1),
  participant_id: z.string().min(1),
  sequence: z.number().int().nonnegative(),
  timestamp: z.string(),
  payload: z.record(z.string(), z.unknown()),
})

export type RoomEvent = z.infer<typeof roomEventSchema>

export function parseRoomEvent(value: unknown): RoomEvent {
  return roomEventSchema.parse(value)
}

// Build the canonical room event envelope the WebSocket protocol expects.
export function roomEvent(
  type: string,
  roomId: string,
  participantId: string,
  sequence: number,
  payload: Record<string, unknown> = {},
): RoomEvent {
  return {
    protocol_version: PROTOCOL_VERSION,
    type,
    event_id: crypto.randomUUID(),
    room_id: roomId,
    participant_id: participantId,
    sequence,
    timestamp: new Date().toISOString(),
    payload,
  }
}

// Downsample a Float32 mic buffer to 16 kHz signed 16-bit PCM (little-endian).
export function toPcm16(input: Float32Array, sampleRate: number): ArrayBuffer {
  const ratio = sampleRate / 16000
  const pcm = new Int16Array(Math.floor(input.length / ratio))
  for (let i = 0; i < pcm.length; i++) {
    const value = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)]))
    pcm[i] = value < 0 ? value * 32768 : value * 32767
  }
  return pcm.buffer
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
