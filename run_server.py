#!/usr/bin/env python3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main() -> None:
    try:
        import uvicorn
    except ImportError as e:
        raise RuntimeError("Uvicorn is not installed. Run: pip install uvicorn fastapi pydantic") from e

    host = os.environ.get("AYEX_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("AYEX_PORT", "8000")))
    uvicorn.run("ayex_api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
