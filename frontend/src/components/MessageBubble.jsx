import { motion } from 'framer-motion';

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
          'max-w-[82%] rounded-2xl border px-4 py-3 text-sm leading-relaxed md:text-[15px]',
          isUser
            ? 'border-cyan-300/40 bg-cyan-400/10 text-cyan-50 shadow-neon'
            : 'border-violet-300/35 bg-violet-500/10 text-slate-100 shadow-violet'
        ].join(' ')}
      >
        <p className="whitespace-pre-wrap">{text}</p>
        {meta ? (
          <div className="mt-2 text-[11px] uppercase tracking-[0.12em] text-slate-300/80">{meta}</div>
        ) : null}
      </div>
    </motion.div>
  );
}
