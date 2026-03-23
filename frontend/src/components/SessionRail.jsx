import { motion } from 'framer-motion';

export default function SessionRail({ sessions, selectedSessionId, onSelectSession, onNewSession }) {
  return (
    <motion.aside
      className="glass-card hidden h-full w-full overflow-hidden md:flex md:flex-col"
      initial={{ x: -18, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: 0.08 }}
    >
      <div className="border-b border-[var(--line)] px-4 py-5">
        <div className="section-kicker">Oturum Zinciri</div>
        <div className="panel-title mt-2 text-2xl text-[var(--text)]">Oturumlar</div>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          Gecmis akisi ac. Mevcut soruyu sadece son mesaja degil, tum oturum dizisine bagla.
        </p>
        <button
          onClick={onNewSession}
          className="soft-button mt-4 h-11 w-full rounded-2xl text-xs tracking-[0.16em]"
        >
          YENI OTURUM
        </button>
      </div>

      <div className="scroll-thin flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {sessions.map((session) => {
          const active = session.id === selectedSessionId;
          return (
            <button
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              className={[
                'w-full rounded-[22px] border px-3 py-3 text-left transition-colors',
                active
                  ? 'border-[rgba(180,138,97,0.34)] bg-[rgba(180,138,97,0.12)]'
                  : 'border-[var(--line)] bg-white/[0.02] hover:border-[var(--line-strong)]'
              ].join(' ')}
            >
              <div className="mb-1 max-h-11 overflow-hidden text-sm font-semibold text-[var(--text)]">{session.title}</div>
              <div className="max-h-[72px] overflow-hidden text-[13px] leading-6 text-[var(--muted)]">{session.last_preview || 'Bos oturum'}</div>
              <div className="mt-2 text-[11px] uppercase tracking-[0.12em] text-[var(--muted)]">
                {formatUpdated(session.updated_at)} • {session.turn_count || 0} tur
              </div>
            </button>
          );
        })}
        {!sessions.length ? (
          <div className="rounded-[22px] border border-dashed border-[var(--line)] px-3 py-4 text-sm leading-6 text-[var(--muted)]">
            Henuz kayitli oturum yok. Ilk mesaji attiginda burada birikmeye baslayacak.
          </div>
        ) : null}
      </div>
    </motion.aside>
  );
}

function formatUpdated(value) {
  if (!value) return 'simdi';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'simdi';
  return new Intl.DateTimeFormat('tr-TR', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}
