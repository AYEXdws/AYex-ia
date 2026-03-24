import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import MessageBubble from './MessageBubble';
import TypingDots from './TypingDots';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const INITIAL_MESSAGE = {
  role: 'assistant',
  text: 'Hazirim. Konuyu net yaz. Gerekirse karar veririm.',
  meta: 'baglam acik • canli akis hazir',
  messageId: '',
  sessionId: '',
  feedback: null,
  responseMode: ''
};

export default function ChatPanel({ token, selectedSessionId, onSessionChange, onStatus, onRefreshSurface, onInsight }) {
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [text, setText] = useState('');
  const [typing, setTyping] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  useEffect(() => {
    async function loadSession() {
      if (!selectedSessionId) {
        setMessages([INITIAL_MESSAGE]);
        onInsight?.(null);
        return;
      }
      setLoadingSession(true);
      try {
        const res = await fetch(`${API_BASE}/sessions/${selectedSessionId}/messages`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || 'Session load failed');
        }
        const mapped = Array.isArray(data?.messages)
          ? data.messages.map((message) => ({
              messageId: message.id,
              sessionId: message.session_id,
              role: message.role,
              text: message.text,
              meta: buildMeta(message.metrics, message.source, message.latency_ms),
              trace: message.metrics?.explainability || null,
              responseMode: message.metrics?.response_mode || '',
              feedback: message.metrics?.decision_feedback || null
            }))
          : [];
        setMessages(mapped.length ? mapped : [INITIAL_MESSAGE]);
        const latestAssistant = [...(data?.messages || [])].reverse().find((message) => message.role === 'assistant');
        onInsight?.(latestAssistant?.metrics?.explainability || null);
      } catch (err) {
        setMessages([
          {
            role: 'assistant',
            text: `Oturum yuklenemedi: ${err.message}`,
            meta: 'session error'
          }
        ]);
      } finally {
        setLoadingSession(false);
      }
    }

    loadSession();
  }, [selectedSessionId, token, onInsight]);

  const canSend = useMemo(() => text.trim().length > 0 && !typing, [text, typing]);
  const promptPresets = [
    'şuan elinde ki canlı veriler nelerdir',
    '1 ay icin hangi coin daha mantikli',
    '1 ay icin hangi hisse daha mantikli',
    'guncel makro tarafta en onemli tablo ne',
  ];

  function applyPreset(value) {
    setText(value);
  }

  async function sendMessage(e) {
    e.preventDefault();
    if (!canSend) return;

    const payloadText = text.trim();
    setText('');
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        text: payloadText,
        meta: 'you',
        messageId: '',
        sessionId: selectedSessionId || '',
        feedback: null,
        responseMode: ''
      }
    ]);
    setTyping(true);
    const started = performance.now();

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          text: payloadText,
          session_id: selectedSessionId || undefined
        })
      });

      const data = await res.json();
      const latency = Math.max(1, Math.round(performance.now() - started));

      if (!res.ok) {
        throw new Error(data?.detail || 'Request failed');
      }
      if (typeof data?.session_id === 'string' && data.session_id.trim()) {
        onSessionChange?.(data.session_id.trim());
      }

      const metrics = data?.metrics || {};
      const model = metrics.used_model || '-';
      const source = metrics.source || '-';
      const mode = metrics.response_style || '-';
      const explainability = metrics.explainability || null;

      onStatus({
        model,
        latency: metrics.latency_ms || latency,
        mode,
        source,
        ready: true
      });
      onInsight?.(explainability);
      onRefreshSurface?.();

      setMessages((prev) => [
        ...prev,
        {
          messageId: String(metrics.message_id || ''),
          sessionId: data.session_id || selectedSessionId || '',
          role: 'assistant',
          text: data.reply || 'No response',
          meta: `${source} • ${metrics.latency_ms || latency} ms • ${mode}`,
          trace: explainability,
          responseMode: metrics.response_mode || '',
          feedback: null
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

  async function submitDecisionFeedback(messageId, sessionId, outcomeStatus) {
    if (!messageId || !sessionId) return false;
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages/${messageId}/decision-feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ outcome_status: outcomeStatus })
    });
    const data = await res.json();
    if (!res.ok || data?.status !== 'ok' || !data?.updated) {
      throw new Error(data?.detail || data?.status || 'Feedback update failed');
    }
    setMessages((prev) =>
      prev.map((message) =>
        message.messageId === messageId
          ? {
              ...message,
              feedback: {
                outcome_status: outcomeStatus,
                note: ''
              }
            }
          : message
      )
    );
    onRefreshSurface?.();
    return true;
  }

  return (
    <div className="glass-card relative flex h-full w-full flex-col overflow-hidden p-5 md:p-6">
      <div className="mb-4 flex flex-col gap-3 border-b border-[var(--line)] pb-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="section-kicker">Desk</div>
          <h2 className="panel-title mt-2 text-2xl text-[var(--text)]">Konusma</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
            Soruyu yaz. Sistem ilgili akisi, hafizayi ve son sinyali birlikte cekip tek cevapta toplasin.
          </p>
        </div>
        <div className="rounded-full border border-[var(--line-strong)] bg-[var(--accent-soft)] px-3 py-1 text-[11px] tracking-[0.16em] text-[var(--accent-strong)]">
          IA
        </div>
      </div>

      <div className="mb-4 grid gap-2 text-xs text-[var(--muted)] md:grid-cols-3">
        <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-3 py-2.5">Baglamli cevap</div>
        <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-3 py-2.5">Hafiza destekli akış</div>
        <div className="rounded-2xl border border-[var(--line)] bg-black/10 px-3 py-2.5">Canli veri ile karar</div>
      </div>

      <div className="mb-4 rounded-[22px] border border-[var(--line)] bg-black/10 px-3 py-3">
        <div className="mb-2 text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Hazir Basliklar</div>
        <div className="flex flex-wrap gap-2">
          {promptPresets.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => applyPreset(preset)}
              className="rounded-full border border-[var(--line)] bg-white/[0.03] px-3 py-2 text-xs text-[var(--muted)] transition-colors hover:border-[var(--line-strong)] hover:text-[var(--text)]"
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto pr-1">
        {loadingSession ? (
          <div className="rounded-[22px] border border-[var(--line)] bg-black/10 px-4 py-3 text-sm text-[var(--muted)]">
            Oturum yukleniyor...
          </div>
        ) : null}
        {messages.map((m, i) => (
          <MessageBubble
            key={m.messageId || `${m.role}-${i}`}
            role={m.role}
            text={m.text}
            meta={m.meta}
            trace={m.trace}
            messageId={m.messageId}
            sessionId={m.sessionId}
            feedback={m.feedback}
            responseMode={m.responseMode}
            onDecisionFeedback={submitDecisionFeedback}
          />
        ))}
        <AnimatePresence>{typing ? <TypingDots key="typing" /> : null}</AnimatePresence>
        <div ref={bottomRef} />
      </div>

      <motion.form
        onSubmit={sendMessage}
        className="mt-4 flex flex-col gap-3 md:flex-row md:items-end"
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="Soruyu yaz. Gerekirse karar, risk ve kanitla birlikte doner."
          className="soft-input min-h-[88px] flex-1 resize-none px-4 py-3 text-sm leading-6"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="soft-button h-12 rounded-2xl px-6 text-xs font-semibold tracking-[0.16em] md:min-w-[160px]"
        >
          GONDER
        </button>
      </motion.form>
    </div>
  );
}

function buildMeta(metrics, source, latency) {
  const safeMetrics = metrics || {};
  const labelSource = safeMetrics.source || source || '-';
  const labelLatency = safeMetrics.latency_ms || latency;
  const labelMode = safeMetrics.response_style || safeMetrics.mode || '';
  return [labelSource, labelLatency ? `${labelLatency} ms` : '', labelMode].filter(Boolean).join(' • ');
}
