import { motion } from 'framer-motion';

function Dot({ active, color }) {
  return (
    <motion.span
      className="inline-block h-2.5 w-2.5 rounded-full"
      style={{ backgroundColor: color, boxShadow: `0 0 14px ${color}` }}
      animate={{ opacity: active ? [0.4, 1, 0.4] : 0.35 }}
      transition={{ duration: 1.8, repeat: Infinity }}
    />
  );
}

export default function StatusPanel({ status, onLogout }) {
  const { model = '-', latency = '-', mode = '-', source = '-', ready = false } = status;
  return (
    <motion.aside
      className="glass-card h-full w-full p-5 md:p-6"
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: 0.15 }}
    >
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="section-kicker">System State</div>
          <h3 className="panel-title mt-2 text-2xl text-[var(--text)]">Durum</h3>
        </div>
        <button
          onClick={onLogout}
          className="rounded-xl border border-[var(--line)] px-3 py-2 text-[10px] tracking-[0.14em] text-[var(--muted)] transition-colors hover:border-[var(--line-strong)]"
        >
          CIKIS
        </button>
      </div>

      <div className="space-y-3">
        <StatusItem label="Model" value={model} />
        <StatusItem label="Latency" value={latency === '-' ? '-' : `${latency} ms`} />
        <StatusItem label="Response" value={mode} />
        <StatusItem label="Source" value={source} />
      </div>

      <div className="mt-8 rounded-[24px] border border-[var(--line)] bg-black/15 p-4">
        <div className="mb-2 text-[11px] tracking-[0.18em] text-[var(--muted)]">RUNTIME</div>
        <div className="flex items-center gap-2 text-sm text-[var(--text)]">
          <Dot active={ready} color={ready ? '#b48a61' : '#6c736f'} />
          {ready ? 'Hazir' : 'Baslatiliyor'}
        </div>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
          Hedef sadece online olmak degil. Tek bir baglam omurgasi ile sana daha net ve daha kararli donmek.
        </p>
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">CHECKPOINT</div>
        <ul className="space-y-2 text-sm text-[var(--text)]">
          <li className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-2">Baglam once, laf sonra</li>
          <li className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-2">Tek cevapta hafiza + veri</li>
          <li className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-2">Dogrudan dil, yapay ton yok</li>
        </ul>
      </div>
    </motion.aside>
  );
}

function StatusItem({ label, value }) {
  return (
    <div className="rounded-[22px] border border-[var(--line)] bg-white/[0.03] px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.13em] text-[var(--muted)]">{label}</div>
      <div className="mt-1 break-words text-[15px] font-medium text-[var(--text)]">{value}</div>
    </div>
  );
}
