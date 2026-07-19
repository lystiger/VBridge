# VBridge demo runbook

Operator guide for judges: bring the server up with Docker and run the live two-phone Vietnamese ↔ English demonstration. Kept separate from the main [README](README.md) so the overview stays focused.

## Quick start

### Lightweight relay stack

You need [Docker with Compose](https://docs.docker.com/compose/install/). The default image is intentionally small: it runs rooms, authentication, encrypted history, device relay, and mock pipeline checks without installing PyTorch or downloading models.

```bash
git clone <your-repository-url>
cd VBridge
docker compose up --build
```

Open:

- Web app: <http://localhost:5173>
- API: <http://localhost:8000>
- Interactive OpenAPI docs: <http://localhost:8000/docs>

### CPU inference stack

The inference override swaps only the API image while preserving the same service name, proxy,
ports, room contract, database, and volumes. Model weights download on first initialization and stay
in the persistent `hf-cache` volume.

```powershell
docker compose -f docker-compose.yml -f docker-compose.inference.yml build api
docker compose -f docker-compose.yml -f docker-compose.inference.yml up -d
```

### CUDA inference stack

This path requires Docker's NVIDIA runtime and a compatible NVIDIA driver:

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.inference.yml `
  -f docker-compose.cuda.yml `
  build api

docker compose `
  -f docker-compose.yml `
  -f docker-compose.inference.yml `
  -f docker-compose.cuda.yml `
  up -d
```

The packaging roles are explicit: `docker/api.Dockerfile` is the lightweight control plane,
`docker/inference.Dockerfile` adds the CPU model stack, and
`docker/inference.cuda.Dockerfile` adds the CUDA/cuDNN runtime and CUDA PyTorch wheels.

### Local development

```powershell
# API — terminal 1
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn apps.api.main:app --reload

# Web — terminal 2
cd apps/web
npm install
npm run dev
```

## Two-phone demo

This is the recommended judging flow for the native Android app connected to the local Docker server. In this path, both phones perform ASR and translation locally, while the server authenticates the participants and relays each canonical translated result.

### 1. Prepare the host computer

Connect the computer and both phones to the same Wi-Fi network. Start the single-worker stack:

```powershell
cd D:\Projects\VBridge
docker compose up -d --build
```

Verify the API before touching the phones:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-WebRequest http://localhost:8000/docs -UseBasicParsing
docker compose ps
```

Expected results:

- `/health` returns HTTP 200.
- The API container is healthy.
- Port `8000` is published by Docker Compose.
- `VBRIDGE_API_WORKERS=1` is active because room state is currently process-local.

Find the LAN address that the phones can reach. The current demo host uses `10.88.216.224`:

```powershell
ipconfig
```

From a phone browser, open `http://10.88.216.224:8000/health`. Do not continue until it responds. Windows Firewall must allow inbound TCP port `8000` on the private network.

### 2. Build and install the Android client

The Android project must be built with the reachable API address:

```properties
VBRIDGE_API_URL=http://10.88.216.224:8000
```

From the Android repository:

```powershell
cd D:\Projects\VBridgeDemo
.\gradlew.bat testDebugUnitTest assembleDebug
```

Install the generated `app\build\outputs\apk\debug\app-debug.apk` on both ARM Android phones. Grant microphone and nearby-device permissions when prompted.

For a USB-only setup, reverse the port on each connected phone and build with `http://127.0.0.1:8000`:

```powershell
adb reverse tcp:8000 tcp:8000
```

An emulator uses `http://10.0.2.2:8000`. A physical phone must not use `localhost`, because that points back to the phone itself.

### 3. Create and join the room

On **Phone A**:

1. Enter the Vietnamese participant's name.
2. Select **Room** connectivity.
3. Select **Create**.
4. Tap **Create Room**.
5. Read the six-character room code from the connected status.

On **Phone B**:

1. Enter the English participant's name.
2. Select **Room** connectivity.
3. Select **Join**.
4. Enter Phone A's six-character code.
5. Tap **Join Room**.

Both phones should display the same room code and a connected state. The server issues a separate signed participant token to each phone; no token is entered manually.

### 4. Run the bilingual demonstration

Use short business-oriented turns so judges can compare the transcript and translation immediately.

1. On Phone A, hold the microphone and say: **“Chúng ta sẽ giao hàng vào thứ Sáu với ngân sách năm mươi triệu đồng.”**
2. Release the microphone. Confirm that both phones show the Vietnamese transcript and English translation, and Phone B speaks the translation.
3. On Phone B, hold the microphone and say: **“Please send the revised contract to Ms. Lan before three PM.”**
4. Release the microphone. Confirm that both phones show the English transcript and Vietnamese translation, and Phone A speaks the translation.
5. Continue for at least three alternating turns, including a name, number, date, and business term.

Hands-on mode is genuine push-to-talk: recording begins on finger-down and ends on release. After the first result, the large microphone becomes compact so it does not cover the conversation timeline. Message times are displayed in GMT+7.

### 5. Show that the server is participating

During the conversation, keep a terminal visible:

```powershell
docker compose logs -f api
```

The proof points for the demo are:

- `POST /rooms` creates the room and owner token.
- `POST /rooms/join` admits the second participant.
- Both phones connect to `/ws/rooms/{room_id}?token=...`.
- Each phone sends `participant.ready`.
- A device-generated `translation.result` is validated and broadcast to both phones with the same `event_id` and server-provided `speaker_id`.
- The sender keeps its successful local result even if relay delivery later fails.

The OpenAPI page at <http://localhost:8000/docs> can be kept open as supporting evidence, but it should not interrupt the conversation flow.

### 6. Failure and fallback demonstration

For a controlled recovery check, briefly stop the API after one successful turn:

```powershell
docker compose stop api
```

The app should retain the local translated bubble and show the room connection failure rather than losing the inference result. Restart the API and allow the WebSocket client to reconnect:

```powershell
docker compose start api
```

If the venue LAN is unreliable, switch both phones to **Bluetooth** mode. Bluetooth uses its own direct RFCOMM transport and does not depend on this server contract. Pre-pair the phones in Android Settings before the presentation.

### Demo success checklist

- [ ] Both phones can open the host's `/health` URL over Wi-Fi.
- [ ] Phone A creates a room and Phone B joins with the displayed code.
- [ ] Both phones show the same translated turns in chronological order.
- [ ] Remote translated speech plays without closing the receiving app.
- [ ] Vietnamese and English speakers can alternate without an operator touching the server.
- [ ] Docker logs show two authenticated WebSocket participants and relayed results.
- [ ] Names, numbers, dates, and business vocabulary survive the live exchange.
- [ ] Bluetooth is paired and ready as the no-network fallback.

> [!IMPORTANT]
> Room state is currently process-local. Keep `VBRIDGE_API_WORKERS=1`. Production startup also requires private room-token and conversation-encryption secrets; the Compose environment used for the demo must configure both.
