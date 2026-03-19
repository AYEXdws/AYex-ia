import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import MessageBubble from './MessageBubble';
import TypingDots from './TypingDots';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function ChatPanel({ token, onStatus }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'AYEX IA active. Komutunu gir.', meta: 'boot • secure channel' }
  ]);
  const [text, setText] = useState('');
  const [typing, setTyping] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  const canSend = useMemo(() => text.trim().length > 0 && !typing, [text, typing]);

  async function sendMessage(e) {
    e.preventDefault();
    if (!canSend) return;

    const payloadText = text.trim();
    setText('');
    setMessages((prev) => [...prev, { role: 'user', text: payloadText, meta: 'you' }]);
    setTyping(true);
    const started = performance.now();

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ text: payloadText })
      });

      const data = await res.json();
      const latency = Math.max(1, Math.round(performance.now() - started));

      if (!res.ok) {
        throw new Error(data?.detail || 'Request failed');
      }

      const metrics = data?.metrics || {};
      const model = metrics.used_model || '-';
      const source = metrics.source || '-';
      const mode = metrics.response_style || '-';

      onStatus({
        model,
        latency: metrics.latency_ms || latency,
        mode,
        source,
        ready: true
      });

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.reply || 'No response',
          meta: `${source} • ${metrics.latency_ms || latency} ms • ${mode}`
        }
      ]);
    } catch (err) {
      onStatus((prev) => ({ ...prev, ready: true, latency: '-' }));
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `System error: ${err.message}`,
          meta: 'error'
        }
      ]);
    } finally {
      setTyping(false);
    }
  }

  return (
    <div className="glass-card relative flex h-full w-full flex-col overflow-hidden p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-wide text-slate-100">Interactive AI Panel</h2>
        <div className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-3 py-1 text-[11px] tracking-[0.15em] text-cyan-100">
          SECURE MODE
        </div>
      </div>

      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.map((m, i) => (
          <MessageBubble key={`${m.role}-${i}`} role={m.role} text={m.text} meta={m.meta} />
        ))}
        <AnimatePresence>{typing ? <TypingDots key="typing" /> : null}</AnimatePresence>
        <div ref={bottomRef} />
      </div>

      <motion.form
        onSubmit={sendMessage}
        className="mt-4 flex items-center gap-3"
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Command AYEX..."
          className="h-12 flex-1 rounded-2xl border border-white/15 bg-black/35 px-4 text-sm text-slate-100 outline-none transition-all duration-300 placeholder:text-slate-500 focus:border-cyan-300/60 focus:shadow-neon"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="h-12 rounded-2xl border border-cyan-300/50 bg-cyan-400/10 px-6 text-xs font-semibold tracking-[0.16em] text-cyan-100 transition-all duration-300 enabled:hover:scale-[1.02] enabled:hover:shadow-neon disabled:cursor-not-allowed disabled:opacity-40"
        >
          SEND
        </button>
      </motion.form>
    </div>
  );
}
