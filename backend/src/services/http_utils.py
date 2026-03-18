from __future__ import annotations

import json
import time
from typing import Callable, Optional
from urllib import error as urlerror


def multipart_body(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    payload: bytes,
) -> tuple[str, bytes]:
    boundary = "----AYEXBoundary"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode())
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(payload)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return boundary, bytes(body)


def is_retryable_http(code: int) -> bool:
    return code == 429 or 500 <= code <= 599


def with_retries(fn: Callable[[], bytes | str], op_name: str, retries: int = 2):
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except urlerror.HTTPError as exc:
            last_err = exc
            if attempt >= retries or not is_retryable_http(exc.code):
                raise RuntimeError(f"{op_name} HTTPError {exc.code}") from exc
        except (urlerror.URLError, TimeoutError) as exc:
            last_err = exc
            if attempt >= retries:
                raise RuntimeError(f"{op_name} baglanti/timeout hatasi: {exc}") from exc
        except Exception as exc:
            last_err = exc
            if attempt >= retries:
                raise
        time.sleep(0.35 * (attempt + 1))
    if last_err is not None:
        raise last_err
    raise RuntimeError(f"{op_name} bilinmeyen hata")


def parse_json_bytes(payload: bytes) -> dict:
    return json.loads(payload.decode("utf-8"))
