# VBridge Phone ↔ Server Shared Contract

**Protocol version:** `1.0.0`

This document is the single source of truth for communication between:

- `VBridgeDemo`: Android application
- `VBridge`: FastAPI server

Both implementations must follow this contract. Do not invent or rename fields independently.

---

## 1. Transport

Use:

- REST for room creation, joining, recovery, and closing
- WebSocket for live room events
- JSON text frames for control and translation events
- Binary WebSocket frames for raw PCM audio in server-inference mode

Base URL:

```text
https://<server-host>
```

Local development example:

```text
http://192.168.1.10:8000
```

WebSocket equivalent:

```text
ws://192.168.1.10:8000
```

---

## 2. Shared values

### Languages

Only use:

```text
vi
en
```

Do not use `vn`, `eng`, `Vietnamese`, or `English` in API payloads.

### Inference modes

```text
device
server
```

- `device`: Android performs ASR and translation, then submits the completed result.
- `server`: Android sends audio and the server performs ASR and translation.

### Audio format

Server-mode audio must use:

```text
Encoding: PCM signed 16-bit little-endian
Sample rate: 16000 Hz
Channels: 1
```

---

## 3. REST API

## 3.1 Create room

```http
POST /api/v1/rooms
Content-Type: application/json
```

Request:

```json
{
  "display_name": "Anh",
  "source_language": "vi",
  "target_language": "en",
  "inference_mode": "device",
  "client": {
    "platform": "android",
    "app_version": "0.1.0",
    "protocol_version": "1.0.0"
  }
}
```

Response:

```json
{
  "protocol_version": "1.0.0",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "room_code": "A7K29Q",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "role": "creator",
  "access_token": "signed-room-token",
  "websocket_url": "wss://server.example/api/v1/ws/rooms/20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "expires_at": "2026-07-19T05:30:00Z"
}
```

---

## 3.2 Join room

```http
POST /api/v1/rooms/join
Content-Type: application/json
```

Request:

```json
{
  "room_code": "A7K29Q",
  "display_name": "John",
  "source_language": "en",
  "target_language": "vi",
  "client": {
    "platform": "android",
    "app_version": "0.1.0",
    "protocol_version": "1.0.0"
  }
}
```

Response:

```json
{
  "protocol_version": "1.0.0",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "room_code": "A7K29Q",
  "participant_id": "be4868fb-8cc9-4422-a287-378b9790d5ae",
  "role": "participant",
  "access_token": "signed-room-token",
  "websocket_url": "wss://server.example/api/v1/ws/rooms/20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "expires_at": "2026-07-19T05:30:00Z"
}
```

---

## 3.3 Get room state

```http
GET /api/v1/rooms/{room_id}
Authorization: Bearer <access_token>
```

Response:

```json
{
  "protocol_version": "1.0.0",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "room_code": "A7K29Q",
  "status": "active",
  "inference_mode": "device",
  "last_room_sequence": 15,
  "participants": [
    {
      "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
      "display_name": "Anh",
      "source_language": "vi",
      "target_language": "en",
      "connected": true
    }
  ]
}
```

---

## 3.4 Close room

```http
DELETE /api/v1/rooms/{room_id}
Authorization: Bearer <access_token>
```

Only the room creator may close the room.

---

## 4. WebSocket connection

Connect using:

```text
wss://<server-host>/api/v1/ws/rooms/{room_id}?token={access_token}
```

Every JSON message uses this envelope:

```json
{
  "protocol_version": "1.0.0",
  "type": "translation.result",
  "event_id": "01JZA8N5ZJ4Z9Y9CX38K7KZ9F4",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 12,
  "room_sequence": 18,
  "timestamp": "2026-07-19T01:30:15.412Z",
  "payload": {}
}
```

### Envelope fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `protocol_version` | string | yes | Must be `1.0.0` |
| `type` | string | yes | Event type |
| `event_id` | string | yes | Globally unique event ID |
| `room_id` | string | yes | Server-issued room ID |
| `participant_id` | string | yes | Server-issued participant ID |
| `sequence` | integer | yes | Sender-local increasing sequence |
| `room_sequence` | integer | server events only | Authoritative room order |
| `timestamp` | ISO-8601 UTC | yes | Event creation time |
| `payload` | object | yes | Event-specific payload |

The client must never send `room_sequence`. The server assigns it.

---

## 5. Connection events

## 5.1 `session.ready`

Sent by Android immediately after WebSocket connection.

```json
{
  "protocol_version": "1.0.0",
  "type": "session.ready",
  "event_id": "01JZA8Q0VRDFSSWMJWZ63BGJGQ",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 1,
  "timestamp": "2026-07-19T01:31:00.000Z",
  "payload": {
    "last_received_room_sequence": 0,
    "supported_audio": {
      "encoding": "pcm_s16le",
      "sample_rates": [16000],
      "channels": [1]
    }
  }
}
```

## 5.2 `session.accepted`

Sent by the server.

```json
{
  "protocol_version": "1.0.0",
  "type": "session.accepted",
  "event_id": "01JZA8Q1236MW8XPP0QHSAJN03",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "server",
  "sequence": 0,
  "room_sequence": 0,
  "timestamp": "2026-07-19T01:31:00.025Z",
  "payload": {
    "heartbeat_interval_ms": 15000,
    "max_turn_duration_ms": 30000,
    "max_audio_bytes": 1048576,
    "inference_mode": "device"
  }
}
```

---

## 6. Device-inference mode

Android performs:

```text
Microphone → VAD → ASR → Translation → Local TTS
```

Then Android sends `translation.submit`.

## 6.1 `translation.submit`

Android → Server

```json
{
  "protocol_version": "1.0.0",
  "type": "translation.submit",
  "event_id": "01JZA91QGZV8J91CSNH8RW5VF6",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 2,
  "timestamp": "2026-07-19T01:32:04.712Z",
  "payload": {
    "turn_id": "01JZA91PCH13XRJ80J0KG9NS3A",
    "source_language": "vi",
    "target_language": "en",
    "transcript": "Xin chào, bạn có khỏe không?",
    "translation": "Hello, how are you?",
    "inference": {
      "mode": "device",
      "asr_engine": "sherpa-onnx",
      "asr_model": "vbridge-asr-vi",
      "translation_engine": "mlkit",
      "tts_engine": "sherpa-onnx"
    },
    "latency_ms": {
      "vad": 54,
      "asr": 820,
      "translation": 137,
      "tts": 210,
      "total": 1221
    }
  }
}
```

The server validates the event, assigns `room_sequence`, and broadcasts `translation.result` to both phones.

---

## 7. Server-inference mode

Android sends audio to the server.

## 7.1 `audio.start`

Android → Server

```json
{
  "protocol_version": "1.0.0",
  "type": "audio.start",
  "event_id": "01JZA9AGH9DCNZF05R24H27B5D",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 3,
  "timestamp": "2026-07-19T01:33:01.000Z",
  "payload": {
    "turn_id": "01JZA9AG8R8KMRHTRQS36C7A98",
    "source_language": "vi",
    "target_language": "en",
    "audio": {
      "encoding": "pcm_s16le",
      "sample_rate_hz": 16000,
      "channels": 1
    }
  }
}
```

## 7.2 Binary audio frames

After `audio.start`, Android sends raw binary PCM frames.

Recommended frame duration:

```text
20–100 ms
```

Do not Base64-encode the audio.

## 7.3 `audio.end`

Android → Server

```json
{
  "protocol_version": "1.0.0",
  "type": "audio.end",
  "event_id": "01JZA9B5AV9NWF7YC0NYG25SV8",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 4,
  "timestamp": "2026-07-19T01:33:03.900Z",
  "payload": {
    "turn_id": "01JZA9AG8R8KMRHTRQS36C7A98",
    "audio_bytes": 92800,
    "duration_ms": 2900
  }
}
```

## 7.4 `audio.queued`

Server → Sending Android client

```json
{
  "protocol_version": "1.0.0",
  "type": "audio.queued",
  "event_id": "01JZA9B5H32EQ2F19KV9GCSEYA",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "server",
  "sequence": 0,
  "timestamp": "2026-07-19T01:33:03.910Z",
  "payload": {
    "turn_id": "01JZA9AG8R8KMRHTRQS36C7A98",
    "queue_position": 1
  }
}
```

---

## 8. Canonical result

Both device and server modes produce the same event.

## 8.1 `translation.result`

Server → Both Android clients

```json
{
  "protocol_version": "1.0.0",
  "type": "translation.result",
  "event_id": "01JZA9EEPHWQ0VHHSAVZZ9S42P",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 4,
  "room_sequence": 17,
  "timestamp": "2026-07-19T01:33:07.016Z",
  "payload": {
    "turn_id": "01JZA9AG8R8KMRHTRQS36C7A98",
    "speaker": {
      "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
      "display_name": "Anh"
    },
    "source_language": "vi",
    "target_language": "en",
    "transcript": "Xin chào, bạn có khỏe không?",
    "translation": "Hello, how are you?",
    "inference": {
      "mode": "server",
      "vad_engine": "silero",
      "asr_engine": "faster-whisper",
      "asr_model": "base",
      "translation_engine": "nllb-200",
      "translation_model": "distilled-600M",
      "tts_engine": "android-local"
    },
    "latency_ms": {
      "queue": 17,
      "vad": 65,
      "asr": 1840,
      "translation": 760,
      "tts": 0,
      "total": 2682
    }
  }
}
```

The receiving Android client should run local TTS using `payload.translation`.

---

## 9. Heartbeat

## 9.1 `ping`

Android → Server

```json
{
  "protocol_version": "1.0.0",
  "type": "ping",
  "event_id": "01JZA9JJ4C70AWRD0AM0MTK4TA",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "b36dc0df-777e-41f4-91ca-4fcb2e960279",
  "sequence": 5,
  "timestamp": "2026-07-19T01:35:00.000Z",
  "payload": {}
}
```

## 9.2 `pong`

Server → Android

```json
{
  "protocol_version": "1.0.0",
  "type": "pong",
  "event_id": "01JZA9JJ66M1H4XM47RJ1E4CD2",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "server",
  "sequence": 0,
  "timestamp": "2026-07-19T01:35:00.011Z",
  "payload": {
    "last_room_sequence": 17
  }
}
```

---

## 10. Error contract

Server errors must use:

```json
{
  "protocol_version": "1.0.0",
  "type": "error",
  "event_id": "01JZA9GW8CKGPB5K5W28Q7S74A",
  "room_id": "20dd98ab-1785-41f3-8f33-f9a49304f3c0",
  "participant_id": "server",
  "sequence": 0,
  "timestamp": "2026-07-19T01:34:00.000Z",
  "payload": {
    "code": "OUT_OF_ORDER_SEQUENCE",
    "message": "Expected sequence 5 but received sequence 7.",
    "retryable": true,
    "related_event_id": "01JZA9GVXAD0T0T6A6VB3MFD00",
    "expected_sequence": 5
  }
}
```

Supported error codes:

```text
INVALID_MESSAGE
UNSUPPORTED_PROTOCOL_VERSION
AUTHENTICATION_FAILED
ROOM_NOT_FOUND
ROOM_FULL
ROOM_CLOSED
DUPLICATE_EVENT
OUT_OF_ORDER_SEQUENCE
INVALID_LANGUAGE_DIRECTION
INVALID_INFERENCE_MODE
AUDIO_FORMAT_UNSUPPORTED
AUDIO_TOO_LARGE
TURN_TOO_LONG
TURN_ALREADY_ACTIVE
INFERENCE_FAILED
RATE_LIMITED
INTERNAL_ERROR
```

---

## 11. Client reliability rules

Android must:

1. Generate a unique `event_id` for every new event.
2. Increase `sequence` for every sent JSON event.
3. Reuse the same `event_id` when retrying the same event.
4. Ignore duplicated `translation.result` events.
5. Store the latest processed `room_sequence`.
6. Send `last_received_room_sequence` during reconnection.
7. Keep successful local translation results even if relay delivery fails.
8. Never send another audio turn while one turn is active.
9. Stop microphone capture during remote playback.
10. Fall back to device translation when remote translation fails, where applicable.

---

## 12. Server validation rules

The server must:

1. Validate the access token and bind it to the room and participant.
2. Reject unknown protocol versions.
3. Reject duplicated `event_id` values without processing twice.
4. Reject invalid or out-of-order client sequences.
5. Ignore any client-supplied `room_sequence`.
6. Assign an authoritative `room_sequence`.
7. Validate the language direction.
8. Enforce room capacity of two participants.
9. Enforce maximum audio duration and size.
10. Broadcast one canonical `translation.result` to both participants.
11. Allow reconnecting clients to recover missed results.
12. Never trust client-supplied speaker names or roles.

---

## 13. Implementation priority

Implement in this order:

1. `POST /api/v1/rooms`
2. `POST /api/v1/rooms/join`
3. Authenticated room WebSocket
4. `session.ready`
5. `session.accepted`
6. `translation.submit`
7. `translation.result`
8. Duplicate event protection
9. Sequence validation
10. Reconnection
11. Server audio streaming
12. Server ASR and translation pipeline

Device relay should work before server inference is added.
