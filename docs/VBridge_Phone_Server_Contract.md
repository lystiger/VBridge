# VBridge Phone ↔ Server Contract

**Protocol version:** `1.0.0`

The machine-readable files are the source of truth:

- [`shared/contract/openapi.json`](../../shared/contract/openapi.json) — REST contract
- [`shared/contract/websocket-client-events.schema.json`](../../shared/contract/websocket-client-events.schema.json) — phone/web-to-server events

Regenerate both after changing a Pydantic contract model:

```powershell
python -m scripts.export_contract
```

The generated files are committed so Android and web builds can generate or validate models without
starting the API. CI tests fail if the WebSocket artifact drifts from its Pydantic source.

## Transport

- REST: room lifecycle under `/rooms`
- WebSocket: `/ws/rooms/{room_id}?token={access_token}`
- JSON text frames: control and result events
- Binary frames: PCM audio after `audio.start` in server-inference rooms

All JSON messages carry `protocol_version: "1.0.0"`. The server currently accepts an omitted version
as `1.0.0` for compatibility, but rejects any other value. New clients must always send it.

## Shared values

- Languages: `vi`, `en`
- Inference modes: `device`, `server`
- Server audio: signed 16-bit little-endian PCM, 16 kHz, mono

## REST flow

Create a room with `POST /rooms`:

```json
{
  "protocol_version": "1.0.0",
  "display_name": "Anh",
  "source_language": "vi",
  "target_language": "en",
  "inference_mode": "device"
}
```

Join with `POST /rooms/join`, adding the six-character `room_code`. Read or close a room with
`GET /rooms/{room_id}` and `DELETE /rooms/{room_id}`, using `Authorization: Bearer <access_token>`.
See OpenAPI for exact request, response, and error shapes.

## WebSocket envelope

```json
{
  "protocol_version": "1.0.0",
  "type": "ping",
  "event_id": "a-unique-id",
  "room_id": "server-issued-room-id",
  "participant_id": "server-issued-participant-id",
  "sequence": 1,
  "timestamp": "2026-07-19T01:35:00Z",
  "payload": {}
}
```

The client event schema is a discriminated union keyed by `type`. It defines these events and validates
their payloads independently:

- `participant.ready`
- `ping`
- `audio.start`
- `audio.end`
- `translation.result`

In `server` mode, send `audio.start`, binary PCM frames, then `audio.end`. In `device` mode, the phone
performs inference and sends `translation.result`; the server validates and relays the canonical result.

Every new event gets a unique `event_id` and a monotonically increasing sender-local `sequence`. Reusing
an event ID is rejected as a duplicate. Identity fields are checked against the authenticated token.

## Client integration

- TypeScript must runtime-validate REST responses and received WebSocket messages.
- Android should generate Kotlin DTOs from `openapi.json` and JSON Schema, or implement serializers with
  tests using the committed schema fixtures.
- Contract changes require a protocol-version decision: backward-compatible additions may remain in
  `1.0.0`; renamed/removed fields or changed semantics require a new version.
