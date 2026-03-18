#!/usr/bin/env python3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ayex_core import AyexAgent
from ayex_core.config import DEFAULT_MODEL


def main() -> None:
    model = os.environ.get("AYEX_MODEL", DEFAULT_MODEL)
    agent = AyexAgent(model=model)
    print("AYEX hazir. Komutlar: /help, /tool, /remember, /coding, /exit")
    while True:
        try:
            user_text = input("\nYou> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGorusmek uzere.")
            return
        if user_text.lower() in {"/exit", "exit", "quit"}:
            print("Gorusmek uzere.")
            return
        reply = agent.safe_handle_input(user_text)
        m = agent.get_last_metrics()
        ms = m.get("latency_ms", "-")
        q = m.get("quality_score", "n/a")
        mode = m.get("mode", "-")
        print(f"\nAYEX> {reply}")
        print(f"     [{ms} ms | kalite {q} | mod {mode}]")


if __name__ == "__main__":
    main()
