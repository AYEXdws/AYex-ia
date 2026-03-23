from __future__ import annotations

import logging
import os
from typing import Any


def get_logger(name: str) -> logging.Logger:
    level_name = os.environ.get("AYEX_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    chunks: list[str] = [f"event={event}"]
    for key in sorted(fields.keys()):
        value = fields.get(key)
        if value is None:
            continue
        text = str(value).replace("\n", " ").strip()
        if not text:
            continue
        chunks.append(f"{key}={text}")
    logger.info("OBS %s", " ".join(chunks))
