from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def web_chat() -> str:
    html = """<!doctype html>
<html lang=\"tr\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>OpenClaw Panel</title>
  <style>
    :root {
      --bg: #f3f5f7;
      --panel: #ffffff;
      --ink: #122028;
      --muted: #5f6f78;
      --line: #d9e0e4;
      --brand: #065f46;
      --brand-2: #0b4f6c;
      --user: #e8f7f2;
      --ayex: #eef4ff;
      --oc: #fff4e8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: \"IBM Plex Sans\", \"Segoe UI\", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 0% 0%, #deefe9 0, transparent 42%),
        radial-gradient(circle at 100% 0%, #dce9f3 0, transparent 38%),
        var(--bg);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 18px;
    }
    .app {
      width: min(940px, 100%);
      height: min(86vh, 920px);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 54px rgba(2, 26, 36, 0.11);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    .top {
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      background: linear-gradient(90deg, #f7fffc, #f7fbff);
    }
    .title { font-weight: 700; letter-spacing: 0.2px; }
    .sub { color: var(--muted); font-size: 13px; }
    .modebar {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-top: 6px;
    }
    select {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 6px 8px;
      font: inherit;
      color: var(--ink);
    }
    .chat {
      padding: 16px;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .row {
      max-width: 85%;
      border-radius: 14px;
      padding: 10px 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      border: 1px solid var(--line);
    }
    .row.user { align-self: flex-end; background: var(--user); }
    .row.ayex { align-self: flex-start; background: var(--ayex); }
    .row.openclaw { align-self: flex-start; background: var(--oc); }
    .composer {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      padding: 14px;
      border-top: 1px solid var(--line);
      background: #fbfcfd;
    }
    textarea {
      width: 100%;
      resize: none;
      height: 64px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 0 16px;
      font-weight: 700;
      color: #fff;
      cursor: pointer;
      background: linear-gradient(135deg, var(--brand), var(--brand-2));
    }
    button:disabled { opacity: 0.55; cursor: wait; }
  </style>
</head>
<body>
  <section class=\"app\">
    <header class=\"top\">
      <div>
        <div class=\"title\">OpenClaw Web Kontrol</div>
        <div class=\"sub\">Tek panelden OpenClaw</div>
        <div class=\"modebar\">
          <label class=\"sub\" for=\"engine\">Motor:</label>
          <select id=\"engine\">
            <option value=\"openclaw\">OpenClaw</option>
          </select>
        </div>
      </div>
      <div style=\"text-align:right;\">
        <div class=\"sub\">Model: __OPENCLAW_MODEL__</div>
        <div id=\"statusText\" class=\"sub\">Durum: Hazır</div>
      </div>
    </header>
    <main id=\"chat\" class=\"chat\">
      <div class=\"row openclaw\">Panel hazır. Mesajını gönder.</div>
    </main>
    <form id=\"form\" class=\"composer\">
      <textarea id=\"text\" placeholder=\"Ahmet için mesaj yaz...\"></textarea>
      <button id=\"send\" type=\"submit\">Gönder</button>
    </form>
  </section>
  <script>
    const chat = document.getElementById("chat");
    const form = document.getElementById("form");
    const text = document.getElementById("text");
    const send = document.getElementById("send");
    const engine = document.getElementById("engine");

    function addRow(kind, value) {
      const el = document.createElement("div");
      el.className = `row ${kind}`;
      el.textContent = value;
      chat.appendChild(el);
      chat.scrollTop = chat.scrollHeight;
      return el;
    }

    function formatMetrics(metrics) {
      if (!metrics) return "ölçüm yok";
      const ms = metrics.latency_ms ?? "-";
      const q = (metrics.quality_score === null || metrics.quality_score === undefined) ? "n/a" : metrics.quality_score;
      const mode = metrics.mode || "-";
      return `${ms} ms | kalite ${q} | mod ${mode}`;
    }

    async function submitMessage(message) {
      send.disabled = true;
      const statusText = document.getElementById("statusText");
      statusText.textContent = "Durum: Düşünüyor...";
      const useEngine = "openclaw";
      const thinkingRow = addRow("openclaw", "Düşünüyorum...");
      try {
        const res = await fetch("/action", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text: message})
        });
        const data = await res.json();
        const reply = data.reply || "OpenClaw yanıt üretmedi.";
        const source = data.source || "openclaw";
        thinkingRow.textContent = `${reply}\n\n(kaynak: ${source})`;
        statusText.textContent = `Durum: Hazır • OpenClaw (${source})`;
      } catch (err) {
        thinkingRow.textContent = "Bağlantı hatası.";
        statusText.textContent = "Durum: Hata";
      } finally {
        send.disabled = false;
      }
    }

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const message = text.value.trim();
      if (!message) return;
      addRow("user", message);
      text.value = "";
      await submitMessage(message);
    });

    text.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        form.requestSubmit();
      }
    });
  </script>
</body>
</html>"""
    openclaw_model = (os.environ.get("OPENCLAW_MODEL") or "openai/gpt-4o-mini").strip()
    return html.replace("__OPENCLAW_MODEL__", openclaw_model)
