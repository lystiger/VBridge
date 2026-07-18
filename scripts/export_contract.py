"""Export the authoritative REST and WebSocket contracts for client generation."""

import json
from pathlib import Path

from apps.api.main import app
from shared.schemas import PROTOCOL_VERSION, ClientRoomEventAdapter

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "shared" / "contract"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    openapi = app.openapi()
    openapi["info"]["x-protocol-version"] = PROTOCOL_VERSION
    write_json(OUTPUT_DIR / "openapi.json", openapi)
    write_json(
        OUTPUT_DIR / "websocket-client-events.schema.json",
        ClientRoomEventAdapter.json_schema(),
    )


if __name__ == "__main__":
    main()
