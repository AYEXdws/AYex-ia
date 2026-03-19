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
  <title>AYEX | Neural Command Deck</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

    :root {
      --bg-0: #06070b;
      --bg-1: #0b1019;
      --bg-2: #111825;
      --ink: #ecf2ff;
      --muted: #8d98ad;
      --line: rgba(185, 202, 233, 0.18);
      --line-strong: rgba(185, 202, 233, 0.32);
      --panel: rgba(11, 15, 24, 0.74);
      --panel-2: rgba(18, 23, 35, 0.64);
      --steel: #c4d1ea;
      --gold: #d6b16b;
      --gold-soft: rgba(214, 177, 107, 0.3);
      --cyan: #27d7ff;
      --cyan-soft: rgba(39, 215, 255, 0.27);
      --danger: #ff6a75;
      --ok: #58f0bb;
      --shadow: 0 26px 60px rgba(0, 0, 0, 0.42);
      --radius-xl: 22px;
      --radius-lg: 16px;
      --radius-md: 12px;
    }

    * { box-sizing: border-box; }

    html, body { height: 100%; }

    body {
      margin: 0;
      color: var(--ink);
      font-family: \"Rajdhani\", \"Trebuchet MS\", sans-serif;
      background:
        radial-gradient(circle at 14% -8%, rgba(25, 125, 180, 0.35), transparent 36%),
        radial-gradient(circle at 86% -14%, rgba(194, 126, 38, 0.22), transparent 32%),
        radial-gradient(circle at 50% 120%, rgba(19, 127, 145, 0.18), transparent 45%),
        linear-gradient(155deg, var(--bg-0), var(--bg-1) 46%, var(--bg-2));
      overflow: hidden;
    }

    .fx-grid::before,
    .fx-grid::after {
      content: \"\";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
    }

    .fx-grid::before {
      background:
        linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: radial-gradient(circle at 50% 40%, black, transparent 86%);
      opacity: 0.18;
    }

    .fx-grid::after {
      background: repeating-linear-gradient(
        180deg,
        rgba(255, 255, 255, 0.018) 0,
        rgba(255, 255, 255, 0.018) 1px,
        transparent 1px,
        transparent 3px
      );
      opacity: 0.2;
      animation: scan 9s linear infinite;
    }

    @keyframes scan {
      from { transform: translateY(-8px); }
      to { transform: translateY(8px); }
    }

    .spotlight {
      position: fixed;
      width: 380px;
      height: 380px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(39, 215, 255, 0.22), transparent 68%);
      pointer-events: none;
      z-index: 1;
      mix-blend-mode: screen;
      transform: translate(-50%, -50%);
      transition: opacity 0.2s ease;
      opacity: 0.65;
    }

    .shell {
      position: relative;
      z-index: 2;
      width: min(1520px, 100vw);
      height: min(980px, 100vh);
      margin: 0 auto;
      padding: clamp(12px, 1.4vw, 24px);
      display: grid;
      grid-template-columns: 356px 1fr;
      gap: 16px;
    }

    .glass {
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background: linear-gradient(138deg, var(--panel), var(--panel-2));
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }

    .rail {
      padding: 14px;
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 12px;
      overflow: hidden;
    }

    .brand {
      border: 1px solid var(--line-strong);
      border-radius: var(--radius-lg);
      background: linear-gradient(130deg, rgba(15, 22, 35, 0.92), rgba(8, 14, 22, 0.82));
      padding: 12px;
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 10px;
    }

    .sigil {
      width: 42px;
      height: 42px;
      border-radius: 12px;
      border: 1px solid var(--gold-soft);
      display: grid;
      place-items: center;
      background: linear-gradient(145deg, rgba(35, 26, 13, 0.86), rgba(22, 28, 40, 0.8));
      font-family: \"Orbitron\", sans-serif;
      font-weight: 900;
      color: var(--gold);
      letter-spacing: 0.8px;
      text-shadow: 0 0 14px rgba(214, 177, 107, 0.4);
    }

    .brand-title {
      font-family: \"Orbitron\", sans-serif;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 1.4px;
      line-height: 1;
    }

    .brand-sub {
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.45px;
      text-transform: uppercase;
    }

    .brand-clock {
      text-align: right;
      font-family: \"Orbitron\", sans-serif;
      font-size: 12px;
      color: var(--steel);
      letter-spacing: 0.8px;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background: linear-gradient(140deg, rgba(13, 18, 29, 0.88), rgba(14, 21, 34, 0.72));
      padding: 12px;
      min-height: 0;
    }

    .card-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    .card-head b {
      font-family: \"Orbitron\", sans-serif;
      color: var(--steel);
      letter-spacing: 0.85px;
      font-size: 12px;
    }

    .profile-tagline {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }

    .profile-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .stat {
      border: 1px solid rgba(189, 206, 237, 0.22);
      border-radius: 10px;
      padding: 8px;
      background: rgba(10, 15, 24, 0.72);
    }

    .stat label {
      display: block;
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.4px;
      margin-bottom: 3px;
      text-transform: uppercase;
    }

    .stat span {
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
      line-height: 1.25;
      word-break: break-word;
    }

    .btn {
      border: 1px solid rgba(195, 214, 247, 0.26);
      border-radius: 10px;
      background: linear-gradient(138deg, rgba(17, 25, 39, 0.95), rgba(18, 27, 42, 0.72));
      color: var(--ink);
      font: inherit;
      font-weight: 700;
      padding: 7px 11px;
      cursor: pointer;
      transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .btn:hover {
      border-color: var(--cyan);
      box-shadow: 0 8px 20px rgba(39, 215, 255, 0.16);
      transform: translateY(-1px);
    }

    .sessions {
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 0;
      overflow: hidden;
    }

    .session-list {
      overflow: auto;
      display: grid;
      gap: 7px;
      padding-right: 2px;
      min-height: 0;
    }

    .session-item {
      border: 1px solid rgba(179, 199, 233, 0.2);
      border-radius: 11px;
      background: linear-gradient(140deg, rgba(9, 14, 23, 0.92), rgba(13, 19, 31, 0.8));
      padding: 9px;
      cursor: pointer;
      transition: border-color 0.14s ease, transform 0.14s ease, box-shadow 0.14s ease;
    }

    .session-item:hover {
      border-color: rgba(39, 215, 255, 0.56);
      transform: translateY(-1px);
    }

    .session-item.active {
      border-color: var(--gold);
      box-shadow: inset 0 0 0 1px rgba(214, 177, 107, 0.28);
      background: linear-gradient(140deg, rgba(30, 22, 14, 0.9), rgba(15, 19, 30, 0.86));
    }

    .session-item b {
      display: block;
      font-size: 14px;
      line-height: 1.2;
      color: #f0f5ff;
      margin-bottom: 2px;
    }

    .session-item span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      text-overflow: ellipsis;
      overflow: hidden;
    }

    .session-meta {
      color: var(--muted);
      font-size: 11px;
      margin-top: 7px;
    }

    .deck {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .chip {
      border: 1px solid rgba(172, 193, 229, 0.27);
      border-radius: 10px;
      padding: 9px;
      background: linear-gradient(145deg, rgba(19, 28, 43, 0.86), rgba(15, 23, 36, 0.8));
      color: var(--ink);
      font: inherit;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      transition: transform 0.12s ease, border-color 0.12s ease;
    }

    .chip:hover {
      border-color: rgba(214, 177, 107, 0.74);
      transform: translateY(-1px);
    }

    .core {
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
    }

    .core-head {
      border-bottom: 1px solid var(--line);
      padding: 14px 16px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: center;
      background: linear-gradient(130deg, rgba(14, 19, 30, 0.86), rgba(13, 18, 28, 0.6));
    }

    .console-title {
      font-family: \"Orbitron\", sans-serif;
      font-weight: 800;
      letter-spacing: 1px;
      font-size: clamp(18px, 1.8vw, 22px);
      line-height: 1.1;
      margin-bottom: 4px;
      text-transform: uppercase;
    }

    .console-sub {
      color: var(--muted);
      font-size: 13px;
    }

    .telemetry {
      display: grid;
      justify-items: end;
      gap: 4px;
      min-width: 260px;
    }

    .status-row {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    .status-orb {
      width: 11px;
      height: 11px;
      border-radius: 50%;
      background: var(--ok);
      box-shadow: 0 0 0 5px rgba(88, 240, 187, 0.14), 0 0 18px rgba(88, 240, 187, 0.46);
      transition: all 0.16s ease;
    }

    .status-orb.busy {
      background: var(--cyan);
      box-shadow: 0 0 0 6px rgba(39, 215, 255, 0.14), 0 0 18px rgba(39, 215, 255, 0.5);
      animation: pulse 1.25s ease infinite;
    }

    .status-orb.error {
      background: var(--danger);
      box-shadow: 0 0 0 6px rgba(255, 106, 117, 0.14), 0 0 18px rgba(255, 106, 117, 0.5);
    }

    @keyframes pulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.18); }
    }

    .status-text {
      font-family: \"Orbitron\", sans-serif;
      color: #d7e4ff;
      letter-spacing: 0.65px;
      font-size: 12px;
    }

    .metric-line,
    .runtime-line,
    .clock-line {
      font-size: 12px;
      color: var(--muted);
    }

    .chat {
      overflow: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-height: 0;
    }

    .msg {
      align-self: flex-start;
      max-width: min(84%, 780px);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: linear-gradient(140deg, rgba(18, 23, 34, 0.94), rgba(17, 21, 32, 0.88));
      white-space: pre-wrap;
      font-size: 17px;
      line-height: 1.45;
      box-shadow: 0 12px 26px rgba(0, 0, 0, 0.22);
      animation: rise 0.2s ease;
    }

    @keyframes rise {
      from { opacity: 0; transform: translateY(8px) scale(0.99); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    .msg.user {
      align-self: flex-end;
      border-color: rgba(39, 215, 255, 0.58);
      background: linear-gradient(145deg, rgba(11, 53, 74, 0.92), rgba(10, 33, 54, 0.94));
    }

    .msg.assistant {
      border-color: rgba(214, 177, 107, 0.46);
      background: linear-gradient(145deg, rgba(42, 33, 20, 0.88), rgba(24, 24, 30, 0.92));
    }

    .msg.thinking {
      border-style: dashed;
      color: #c7d3ea;
      font-style: italic;
    }

    .msg-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 7px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .msg-meta {
      margin-top: 8px;
      font-size: 11px;
      color: #9aacc8;
      letter-spacing: 0.2px;
    }

    .composer {
      border-top: 1px solid var(--line);
      background: linear-gradient(140deg, rgba(10, 14, 23, 0.92), rgba(12, 17, 27, 0.84));
      padding: 12px;
      display: grid;
      gap: 10px;
    }

    .composer-main {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
    }

    textarea {
      width: 100%;
      min-height: 76px;
      max-height: 220px;
      resize: vertical;
      border-radius: 14px;
      border: 1px solid rgba(191, 209, 240, 0.32);
      background: rgba(10, 16, 25, 0.94);
      color: var(--ink);
      font: inherit;
      font-size: 18px;
      line-height: 1.36;
      padding: 12px 14px;
      outline: none;
      transition: border-color 0.14s ease, box-shadow 0.14s ease;
    }

    textarea:focus {
      border-color: rgba(39, 215, 255, 0.8);
      box-shadow: 0 0 0 2px rgba(39, 215, 255, 0.18);
    }

    .send {
      border: 0;
      border-radius: 14px;
      min-width: 138px;
      padding: 0 18px;
      font: inherit;
      font-weight: 800;
      font-size: 16px;
      color: #091018;
      cursor: pointer;
      background: linear-gradient(145deg, #f5cd85, #dca85d 42%, #b5833e);
      box-shadow: 0 16px 24px rgba(193, 133, 58, 0.28);
      transition: transform 0.12s ease, filter 0.12s ease;
    }

    .send:hover { transform: translateY(-1px); filter: brightness(1.05); }
    .send:disabled { opacity: 0.62; cursor: wait; }

    .composer-foot {
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      gap: 10px;
    }

    .kbd {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 26px;
      padding: 2px 7px;
      border-radius: 7px;
      border: 1px solid rgba(183, 201, 232, 0.28);
      background: rgba(20, 26, 39, 0.8);
      color: #e2edff;
      font-family: \"Orbitron\", sans-serif;
      font-size: 10px;
      letter-spacing: 0.5px;
    }

    @media (max-width: 1120px) {
      body { overflow: auto; }
      .spotlight { display: none; }
      .shell {
        width: 100%;
        height: auto;
        grid-template-columns: 1fr;
      }
      .sessions { min-height: 240px; }
      .msg { max-width: 95%; }
      .telemetry { justify-items: start; }
      .core-head { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class=\"fx-grid\" aria-hidden=\"true\"></div>
  <div class=\"spotlight\" id=\"spotlight\" aria-hidden=\"true\"></div>

  <main class=\"shell\">
    <aside class=\"rail glass\">
      <section class=\"brand\">
        <div class=\"sigil\">AX</div>
        <div>
          <div class=\"brand-title\">AYEX</div>
          <div class=\"brand-sub\">Neural Command Interface</div>
        </div>
        <div class=\"brand-clock\" id=\"clock\">--:--:--</div>
      </section>

      <section class=\"card\">
        <div class=\"card-head\"><b>OPERATÖR PROFİLİ</b></div>
        <div class=\"profile-tagline\" id=\"tagline\">Profil eşleşmesi hazırlanıyor...</div>
        <div class=\"profile-grid\">
          <div class=\"stat\"><label>İsim</label><span id=\"pName\">-</span></div>
          <div class=\"stat\"><label>Hitap</label><span id=\"pCall\">-</span></div>
          <div class=\"stat\"><label>Hedef</label><span id=\"pGoal\">-</span></div>
          <div class=\"stat\"><label>Odak</label><span id=\"pFocus\">-</span></div>
        </div>
      </section>

      <section class=\"card sessions\">
        <div class=\"card-head\">
          <b>SOHBET ARŞİVİ</b>
          <button class=\"btn\" id=\"newSession\" type=\"button\">+ Yeni</button>
        </div>
        <div class=\"session-list\" id=\"sessionList\"></div>
        <div class=\"session-meta\" id=\"sessionMeta\">0 aktif kayıt</div>
      </section>

      <section class=\"deck\">
        <button class=\"chip\" data-prompt=\"Bugun icin net bir operasyon plani cikart.\">Operasyon Planı</button>
        <button class=\"chip\" data-prompt=\"Fikrimi zayif noktalarina gore sert sekilde analiz et.\">Sert Analiz</button>
        <button class=\"chip\" data-prompt=\"Bu haftayi kazanca donusturecek 3 strateji ver.\">Kazanç Rotası</button>
        <button class=\"chip\" data-prompt=\"Bugun hangi tek hamleyi yapmaliyim?\">Tek Hamle</button>
      </section>
    </aside>

    <section class=\"core glass\">
      <header class=\"core-head\">
        <div>
          <div class=\"console-title\">AYEX Tactical Deck</div>
          <div class=\"console-sub\">AYEX cekirdek kilidi aktif | Sadece AYEX deneyimi</div>
        </div>

        <div class=\"telemetry\">
          <div class=\"status-row\">
            <span class=\"status-orb\" id=\"statusOrb\"></span>
            <span class=\"status-text\" id=\"status\">Hazır</span>
          </div>
          <div class=\"metric-line\" id=\"metrics\">gecikme: - | cache: - | context: - | memory: -</div>
          <div class=\"runtime-line\" id=\"runtimeModel\">runtime model: -</div>
          <div class=\"clock-line\" id=\"hudClock\">--:--:--</div>
        </div>
      </header>

      <section class=\"chat\" id=\"chat\"></section>

      <form class=\"composer\" id=\"form\">
        <div class=\"composer-main\">
          <textarea id=\"text\" placeholder=\"AYEX icin komutunu yaz...\"></textarea>
          <button class=\"send\" id=\"send\" type=\"submit\">Ateşle</button>
        </div>
        <div class=\"composer-foot\">
          <span><span class=\"kbd\">ENTER</span> gonderir, <span class=\"kbd\">SHIFT</span> + <span class=\"kbd\">ENTER</span> satir atlar.</span>
          <span id=\"charCount\">0 karakter</span>
        </div>
      </form>
    </section>
  </main>

  <script>
    const state = {
      sessionId: null,
      busy: false,
      profile: null,
    };

    const chatEl = document.getElementById('chat');
    const sessionListEl = document.getElementById('sessionList');
    const sessionMetaEl = document.getElementById('sessionMeta');
    const textEl = document.getElementById('text');
    const sendEl = document.getElementById('send');
    const statusEl = document.getElementById('status');
    const statusOrbEl = document.getElementById('statusOrb');
    const metricsEl = document.getElementById('metrics');
    const runtimeModelEl = document.getElementById('runtimeModel');
    const charCountEl = document.getElementById('charCount');
    const expectedModel = '__OPENCLAW_MODEL__';
    const spotlightEl = document.getElementById('spotlight');

    function nowClock() {
      const d = new Date();
      return d.toLocaleTimeString('tr-TR', {hour12: false});
    }

    function tickClock() {
      const val = nowClock();
      document.getElementById('clock').textContent = val;
      document.getElementById('hudClock').textContent = val;
    }

    setInterval(tickClock, 1000);
    tickClock();

    document.addEventListener('pointermove', (ev) => {
      spotlightEl.style.left = ev.clientX + 'px';
      spotlightEl.style.top = ev.clientY + 'px';
    });

    function updateCharCount() {
      charCountEl.textContent = `${textEl.value.length} karakter`;
    }

    textEl.addEventListener('input', updateCharCount);
    updateCharCount();

    async function api(path, options = {}) {
      const res = await fetch(path, {
        headers: {'Content-Type': 'application/json'},
        ...options,
      });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
      if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
      return data;
    }

    function setStatus(text, mode = 'ready') {
      statusEl.textContent = text;
      statusOrbEl.classList.remove('busy', 'error');
      if (mode === 'busy') {
        statusOrbEl.classList.add('busy');
      } else if (mode === 'error') {
        statusOrbEl.classList.add('error');
      }
    }

    function setMetrics(metrics = {}) {
      const latency = metrics.latency_ms ?? '-';
      const cache = metrics.cache_hit ? 'hit' : 'miss';
      const ctx = metrics.context_messages ?? '-';
      const memory = metrics.memory_hits ?? 0;
      metricsEl.textContent = `gecikme: ${latency} ms | cache: ${cache} | context: ${ctx} | memory: ${memory}`;

      const used = metrics.used_model || '';
      const locked = metrics.model_locked ? 'locked' : 'unlocked';
      runtimeModelEl.textContent = `runtime core: secure (${locked})`;
      if (used && used !== expectedModel) {
        runtimeModelEl.style.color = 'var(--danger)';
        runtimeModelEl.textContent = `runtime core: cekirdek sapmasi (${locked})`;
      } else {
        runtimeModelEl.style.color = 'var(--muted)';
      }
    }

    function clearChat() {
      chatEl.innerHTML = '';
    }

    function messageBubble(role, text, meta = {}) {
      const box = document.createElement('div');
      box.className = `msg ${role}`;

      const head = document.createElement('div');
      head.className = 'msg-head';

      const who = document.createElement('span');
      who.textContent = role === 'user' ? 'sen' : 'ayex';

      const when = document.createElement('span');
      if (meta.ts) {
        when.textContent = new Date(meta.ts).toLocaleTimeString('tr-TR', {hour: '2-digit', minute: '2-digit'});
      } else {
        when.textContent = new Date().toLocaleTimeString('tr-TR', {hour: '2-digit', minute: '2-digit'});
      }

      head.appendChild(who);
      head.appendChild(when);
      box.appendChild(head);

      const body = document.createElement('div');
      body.textContent = text;
      box.appendChild(body);

      const parts = [];
      if (meta.source) parts.push(meta.source);
      if (meta.latency_ms !== undefined && meta.latency_ms !== null) parts.push(`${meta.latency_ms} ms`);
      if (meta.cache_hit) parts.push('cache-hit');

      if (parts.length > 0) {
        const metaEl = document.createElement('div');
        metaEl.className = 'msg-meta';
        metaEl.textContent = parts.join(' • ');
        box.appendChild(metaEl);
      }

      chatEl.appendChild(box);
      chatEl.scrollTop = chatEl.scrollHeight;
      return box;
    }

    function renderProfile(profile) {
      document.getElementById('pName').textContent = profile.name || 'Ahmet';
      const calls = Array.isArray(profile.preferred_calls) ? profile.preferred_calls.join(', ') : 'Ahmet';
      document.getElementById('pCall').textContent = calls || 'Ahmet';
      document.getElementById('pGoal').textContent = profile.goal || 'Belirtilmedi';
      const focus = Array.isArray(profile.focus_projects) ? profile.focus_projects[0] : '';
      document.getElementById('pFocus').textContent = (focus || 'AYEX').slice(0, 28);
      document.getElementById('tagline').textContent = profile.communication_tone || 'Net, sert, stratejik iletisim';
    }

    function renderSessions(sessions = []) {
      sessionListEl.innerHTML = '';
      sessionMetaEl.textContent = `${sessions.length} kayit`;

      if (sessions.length === 0) {
        const d = document.createElement('div');
        d.className = 'session-item';
        d.innerHTML = '<b>Kayit bulunmadi</b><span>Yeni sohbet ac</span>';
        sessionListEl.appendChild(d);
        return;
      }

      for (const s of sessions) {
        const el = document.createElement('div');
        el.className = 'session-item' + (s.id === state.sessionId ? ' active' : '');
        el.innerHTML = `<b>${s.title || 'Yeni Sohbet'}</b><span>${s.last_preview || 'Mesaj bekleniyor'}</span>`;
        el.addEventListener('click', () => selectSession(s.id));
        sessionListEl.appendChild(el);
      }
    }

    async function refreshSessions() {
      const data = await api('/sessions?limit=40');
      const sessions = data.sessions || [];
      if (!state.sessionId && sessions.length > 0) {
        state.sessionId = sessions[0].id;
      }
      renderSessions(sessions);
      return sessions;
    }

    async function createSession(title = null) {
      const data = await api('/sessions', {
        method: 'POST',
        body: JSON.stringify({title}),
      });
      state.sessionId = data.id;
      await refreshSessions();
      await loadMessages(state.sessionId);
    }

    async function loadMessages(sessionId) {
      if (!sessionId) return;
      const data = await api(`/sessions/${sessionId}/messages?limit=250`);
      clearChat();
      const messages = data.messages || [];
      if (messages.length === 0) {
        messageBubble('assistant', 'AYEX hazir. Komutunu bekliyorum.', {source: 'ayex'});
      } else {
        for (const msg of messages) {
          const role = msg.role === 'user' ? 'user' : 'assistant';
          const meta = Object.assign({}, msg, msg.metrics || {});
          messageBubble(role, msg.text, meta);
        }
      }
      chatEl.scrollTop = chatEl.scrollHeight;
    }

    async function selectSession(sessionId) {
      state.sessionId = sessionId;
      await refreshSessions();
      await loadMessages(sessionId);
    }

    async function submitMessage(message) {
      if (state.busy) return;
      if (!state.sessionId) await createSession();

      state.busy = true;
      sendEl.disabled = true;
      setStatus('Düşünüyor...', 'busy');

      messageBubble('user', message, {source: 'sen'});
      const loading = messageBubble('assistant thinking', 'AYEX analiz yapiyor...');

      try {
        const data = await api('/action', {
          method: 'POST',
          body: JSON.stringify({
            text: message,
            session_id: state.sessionId,
            use_profile: true,
          }),
        });

        state.sessionId = data.session_id || state.sessionId;
        loading.className = 'msg assistant';
        loading.innerHTML = '';

        const body = document.createElement('div');
        body.textContent = data.reply || 'Yanit yok.';
        loading.appendChild(body);

        const m = data.metrics || {};
        const meta = document.createElement('div');
        meta.className = 'msg-meta';
        meta.textContent = `${m.latency_ms ?? '-'} ms • ${m.cache_hit ? 'cache-hit' : 'live'} • context ${m.context_messages ?? '-'} • memory ${m.memory_hits ?? 0}`;
        loading.appendChild(meta);

        setStatus(data.status === 'ok' ? 'Hazır' : 'Uyarı', data.status === 'ok' ? 'ready' : 'error');
        setMetrics(m);
        await refreshSessions();
      } catch (err) {
        loading.className = 'msg assistant';
        loading.innerHTML = '';
        const body = document.createElement('div');
        body.textContent = 'Baglanti veya istek hatasi.';
        loading.appendChild(body);
        setStatus('Hata', 'error');
      } finally {
        state.busy = false;
        sendEl.disabled = false;
        textEl.focus();
      }
    }

    document.getElementById('form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const message = textEl.value.trim();
      if (!message) return;
      textEl.value = '';
      await submitMessage(message);
    });

    textEl.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        document.getElementById('form').requestSubmit();
      }
    });

    document.addEventListener('keydown', (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') {
        ev.preventDefault();
        textEl.focus();
      }
    });

    document.getElementById('newSession').addEventListener('click', async () => {
      await createSession();
      textEl.focus();
    });

    document.querySelectorAll('.chip').forEach((chip) => {
      chip.addEventListener('click', async () => {
        const prompt = chip.getAttribute('data-prompt') || '';
        if (!prompt) return;
        textEl.value = prompt;
        await submitMessage(prompt);
        textEl.value = '';
      });
    });

    async function bootstrap() {
      try {
        const profileData = await api('/profile');
        renderProfile(profileData.profile || {});
      } catch (_) {
        document.getElementById('tagline').textContent = 'Profil okunamadi.';
      }

      const sessions = await refreshSessions();
      if (sessions.length === 0) {
        await createSession();
      } else {
        await selectSession(state.sessionId || sessions[0].id);
      }
      setStatus('Hazır', 'ready');
      setMetrics({});
      textEl.focus();
    }

    bootstrap();
  </script>
</body>
</html>"""
    openclaw_model = (os.environ.get("OPENCLAW_MODEL") or "openai/gpt-4o-mini").strip()
    return html.replace("__OPENCLAW_MODEL__", openclaw_model).replace("__OPENCLAW_MODEL__", openclaw_model)
