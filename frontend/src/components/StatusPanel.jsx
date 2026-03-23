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

export default function StatusPanel({ status, intelBrief, insight, onLogout }) {
  const { model = '-', latency = '-', mode = '-', source = '-', ready = false } = status;
  const proactive = intelBrief?.proactive || null;
  const marketFocus = intelBrief?.market_focus || null;
  const domainFocus = intelBrief?.domain_focus || null;
  const liveInventory = intelBrief?.live_inventory?.feeds || null;
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
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">PROAKTIF BRIEF</div>
        <p className="text-sm leading-6 text-[var(--text)]">
          {proactive?.summary || 'Guncel brief henuz yuklenmedi.'}
        </p>
        {proactive?.priorities?.length ? (
          <div className="mt-3 space-y-2">
            {proactive.priorities.slice(0, 3).map((item) => (
              <div key={item} className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-2 text-sm text-[var(--muted)]">
                {item}
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">NET KARARLAR</div>
        <div className="space-y-3">
          <DecisionCard
            label="Kripto"
            summary={marketFocus?.crypto?.summary}
            reasons={marketFocus?.crypto?.reasons}
          />
          <DecisionCard
            label="Hisse"
            summary={marketFocus?.equities?.summary}
            reasons={marketFocus?.equities?.reasons}
          />
          <DecisionCard
            label="Makro"
            summary={marketFocus?.macro?.summary}
            reasons={marketFocus?.macro?.reasons}
          />
        </div>
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">ASSET SINYALLERI</div>
        <SignalGroup label="Kripto" rows={marketFocus?.crypto_signals} />
        <SignalGroup label="Hisse" rows={marketFocus?.equities_signals} />
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">CANLI FEED ODAKLARI</div>
        <div className="space-y-3">
          <DecisionCard
            label="World"
            summary={domainFocus?.world?.summary}
            reasons={domainFocus?.world?.reasons}
          />
          <DecisionCard
            label="Cyber"
            summary={domainFocus?.cyber?.summary}
            reasons={domainFocus?.cyber?.reasons}
          />
        </div>
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">FEED FRESHNESS</div>
        <div className="space-y-3">
          <FeedRow label="Kripto" row={liveInventory?.crypto} />
          <FeedRow label="Hisse" row={liveInventory?.equities} />
          <FeedRow label="Makro" row={liveInventory?.macro} />
          <FeedRow label="World" row={liveInventory?.world} />
          <FeedRow label="Cyber" row={liveInventory?.cyber} />
        </div>
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">SON CEVABIN GEREKCESI</div>
        <p className="text-sm leading-6 text-[var(--muted)]">
          {insight?.decision || insight?.briefing || 'Yeni bir cevap geldiginde neden bu yone gittigini burada goreceksin.'}
        </p>
        {insight?.memory?.length ? <ReasonList title="Hafiza izleri" items={insight.memory} /> : null}
        {insight?.intel?.length ? <ReasonList title="Intel izleri" items={insight.intel} /> : null}
        {insight?.reasons?.length ? <ReasonList title="Karar gerekcesi" items={insight.reasons} /> : null}
        {insight?.risks?.length ? <ReasonList title="Riskler" items={insight.risks} /> : null}
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

function ReasonList({ title, items }) {
  return (
    <div className="mt-4">
      <div className="mb-2 text-[11px] uppercase tracking-[0.15em] text-[var(--accent-strong)]">{title}</div>
      <div className="space-y-2">
        {items.slice(0, 3).map((item, index) => (
          <div key={`${title}-${index}`} className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-2 text-sm leading-6 text-[var(--text)]">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function DecisionCard({ label, summary, reasons }) {
  const rows = Array.isArray(reasons) ? reasons.filter(Boolean).slice(0, 2) : [];
  return (
    <div className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--accent-strong)]">{label}</div>
      <div className="mt-2 text-sm leading-6 text-[var(--text)]">
        {summary || 'Net karar sinyali henuz yok.'}
      </div>
      {rows.length ? (
        <div className="mt-2 space-y-2">
          {rows.map((item, index) => (
            <div key={`${label}-${index}`} className="text-sm leading-6 text-[var(--muted)]">
              {item}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SignalGroup({ label, rows }) {
  const items = Array.isArray(rows) ? rows.slice(0, 3) : [];
  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-2 text-[11px] uppercase tracking-[0.14em] text-[var(--accent-strong)]">{label}</div>
      {items.length ? (
        <div className="space-y-2">
          {items.map((row) => (
            <div key={`${label}-${row.asset}`} className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium text-[var(--text)]">{row.asset}</div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">
                  {row.stance} · {row.score}
                </div>
              </div>
              <div className="mt-2 text-sm leading-6 text-[var(--text)]">{row.summary}</div>
              {row.reasons?.length ? (
                <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{row.reasons[0]}</div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3 text-sm text-[var(--muted)]">
          Henuz asset bazli sinyal yok.
        </div>
      )}
    </div>
  );
}

function FeedRow({ label, row }) {
  const freshness = row?.freshness || 'unknown';
  const count = row?.count_24h ?? 0;
  const summary = row?.summary || 'Veri yok.';
  return (
    <div className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-[var(--text)]">{label}</div>
        <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">
          {freshness} · {count}/24s
        </div>
      </div>
      <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{summary}</div>
    </div>
  );
}
