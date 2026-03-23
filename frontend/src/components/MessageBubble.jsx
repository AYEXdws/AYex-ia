import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';

export default function MessageBubble({ role, text, meta, trace }) {
  const isUser = role === 'user';
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
        {!isUser && trace ? <TraceBlock trace={trace} /> : null}
      </div>
    </motion.div>
  );
}

function TraceBlock({ trace }) {
  const reasons = Array.isArray(trace?.reasons) ? trace.reasons : [];
  const risks = Array.isArray(trace?.risks) ? trace.risks : [];
  const memory = Array.isArray(trace?.memory) ? trace.memory : [];
  const intel = Array.isArray(trace?.intel) ? trace.intel : [];
  const briefing = trace?.briefing || '';
  const decision = trace?.decision || '';

  if (!reasons.length && !risks.length && !memory.length && !intel.length && !briefing && !decision) {
    return null;
  }

  return (
    <div className="mt-3 rounded-[18px] border border-[var(--line)] bg-black/10 px-3 py-3">
      <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">neden boyle cevap verdi</div>
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
