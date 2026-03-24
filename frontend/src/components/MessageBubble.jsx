import { motion } from 'framer-motion';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

const DECISION_FEEDBACK_OPTIONS = [
  ['dogru', 'Dogru'],
  ['yanlis', 'Yanlis'],
  ['beklemede', 'Beklemede'],
  ['gecersiz', 'Gecersiz'],
];

export default function MessageBubble({
  role,
  text,
  meta,
  trace,
  messageId,
  sessionId,
  feedback,
  responseMode,
  onDecisionFeedback,
}) {
  const isUser = role === 'user';
  const showDecisionFeedback = !isUser && responseMode === 'decision' && messageId && sessionId;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={[
          'max-w-[88%] rounded-[24px] border px-4 py-3 text-sm leading-relaxed md:text-[15px]',
          isUser
            ? 'border-[rgba(180,138,97,0.28)] bg-[rgba(180,138,97,0.14)] text-[var(--text)]'
            : 'border-[var(--line)] bg-[rgba(255,255,255,0.03)] text-[var(--text)]'
        ].join(' ')}
      >
        <div className="message-content whitespace-pre-wrap">
          <ReactMarkdown>{text}</ReactMarkdown>
        </div>
        {meta ? (
          <div className="mt-2 text-[11px] uppercase tracking-[0.12em] text-[var(--muted)]">{meta}</div>
        ) : null}
        {showDecisionFeedback ? (
          <DecisionFeedbackBar
            messageId={messageId}
            sessionId={sessionId}
            feedback={feedback}
            onDecisionFeedback={onDecisionFeedback}
          />
        ) : null}
        {!isUser && trace ? <TraceBlock trace={trace} /> : null}
      </div>
    </motion.div>
  );
}

function DecisionFeedbackBar({ messageId, sessionId, feedback, onDecisionFeedback }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const selected = String(feedback?.outcome_status || '').trim().toLowerCase();

  async function handleClick(outcomeStatus) {
    if (!onDecisionFeedback || busy || selected === outcomeStatus) return;
    setBusy(outcomeStatus);
    setError('');
    try {
      await onDecisionFeedback(messageId, sessionId, outcomeStatus);
    } catch (err) {
      setError(err.message || 'Feedback kaydedilemedi');
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="mt-3 rounded-[18px] border border-[var(--line)] bg-black/10 px-3 py-3">
      <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">karar geri bildirimi</div>
      <div className="flex flex-wrap gap-2">
        {DECISION_FEEDBACK_OPTIONS.map(([value, label]) => {
          const active = selected === value;
          return (
            <button
              key={value}
              type="button"
              disabled={Boolean(busy)}
              onClick={() => handleClick(value)}
              className={[
                'rounded-full border px-3 py-2 text-[11px] uppercase tracking-[0.12em] transition-colors',
                active
                  ? 'border-[var(--accent-strong)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                  : 'border-[var(--line)] bg-white/[0.03] text-[var(--muted)] hover:border-[var(--line-strong)] hover:text-[var(--text)]',
                busy && !active ? 'opacity-60' : '',
              ].join(' ')}
            >
              {busy === value ? 'Kaydediliyor' : label}
            </button>
          );
        })}
      </div>
      {selected ? (
        <div className="mt-2 text-[12px] leading-5 text-[var(--muted)]">
          Son durum: <span className="text-[var(--text)]">{selected}</span>
        </div>
      ) : null}
      {error ? <div className="mt-2 text-[12px] leading-5 text-[#d59378]">{error}</div> : null}
    </div>
  );
}

function TraceBlock({ trace }) {
  const reasons = Array.isArray(trace?.reasons) ? trace.reasons : [];
  const risks = Array.isArray(trace?.risks) ? trace.risks : [];
  const memory = Array.isArray(trace?.memory) ? trace.memory : [];
  const intel = Array.isArray(trace?.intel) ? trace.intel : [];
  const briefing = trace?.briefing || '';
  const decision = trace?.decision || '';
  const responseMode = trace?.response_mode || '';

  if (!reasons.length && !risks.length && !memory.length && !intel.length && !briefing && !decision && !responseMode) {
    return null;
  }

  return (
    <div className="mt-3 rounded-[18px] border border-[var(--line)] bg-black/10 px-3 py-3">
      <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">cevap izleri</div>
      {responseMode ? <TraceLine label="Mod" value={responseMode} /> : null}
      {decision ? <TraceLine label="Karar" value={decision} /> : null}
      {briefing ? <TraceLine label="Brief" value={briefing} /> : null}
      {reasons.length ? <TraceList label="Gerekce" items={reasons} /> : null}
      {risks.length ? <TraceList label="Risk" items={risks} /> : null}
      {memory.length ? <TraceList label="Hafiza" items={memory} /> : null}
      {intel.length ? <TraceList label="Intel" items={intel} /> : null}
    </div>
  );
}

function TraceLine({ label, value }) {
  return (
    <div className="mb-2 text-[13px] leading-6 text-[var(--muted)]">
      <span className="mr-2 text-[var(--accent-strong)]">{label}:</span>
      <span>{value}</span>
    </div>
  );
}

function TraceList({ label, items }) {
  return (
    <div className="mb-2">
      <div className="mb-1 text-[11px] uppercase tracking-[0.15em] text-[var(--accent-strong)]">{label}</div>
      <div className="space-y-1 text-[13px] leading-6 text-[var(--muted)]">
        {items.map((item, index) => (
          <div key={`${label}-${index}`}>- {item}</div>
        ))}
      </div>
    </div>
  );
}
