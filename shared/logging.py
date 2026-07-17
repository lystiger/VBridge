import json
import logging
from datetime import UTC, datetime
from typing import Any


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(event: str, **context: Any) -> None:
    logging.getLogger("vbridge").info(
        json.dumps(
            {"timestamp": datetime.now(UTC).isoformat(), "event": event, **context},
            default=str,
        )
    )
