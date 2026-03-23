import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';

export default function MessageBubble({ role, text, meta }) {
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
      </div>
    </motion.div>
  );
}
