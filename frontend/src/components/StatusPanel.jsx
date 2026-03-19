import { motion } from 'framer-motion';

function Dot({ active, color }) {
  return (
    <motion.span
      className="inline-block h-2.5 w-2.5 rounded-full"
      style={{ backgroundColor: color, boxShadow: `0 0 16px ${color}` }}
      animate={{ opacity: active ? [0.4, 1, 0.4] : 0.35 }}
      transition={{ duration: 1.8, repeat: Infinity }}
    />
  );
}

export default function StatusPanel({ status, onLogout }) {
  const { model = '-', latency = '-', mode = '-', source = '-', ready = false } = status;
  return (
    <motion.aside
      className="glass-card h-full w-full max-w-[290px] p-5"
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: 0.15 }}
    >
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-xs tracking-[0.28em] text-slate-300">SYSTEM STATUS</h3>
        <button
          onClick={onLogout}
          className="rounded-lg border border-white/15 px-2.5 py-1 text-[10px] tracking-[0.14em] text-slate-300 hover:border-cyan-300/40"
        >
          LOGOUT
        </button>
      </div>

      <div className="space-y-3">
        <StatusItem label="Model" value={model} />
        <StatusItem label="Latency" value={latency === '-' ? '-' : `${latency} ms`} />
        <StatusItem label="Mode" value={mode} />
        <StatusItem label="Source" value={source} />
      </div>

      <div className="mt-8 rounded-xl border border-white/10 bg-black/30 p-3">
        <div className="mb-2 text-[11px] tracking-[0.18em] text-slate-400">RUNTIME</div>
        <div className="flex items-center gap-2 text-sm text-slate-200">
          <Dot active={ready} color={ready ? '#00F0FF' : '#8b9ab3'} />
          {ready ? 'Online' : 'Initializing'}
        </div>
      </div>
    </motion.aside>
  );
}

function StatusItem({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-[0.13em] text-slate-400">{label}</div>
      <div className="mt-1 text-[15px] font-medium text-slate-100">{value}</div>
    </div>
  );
}
