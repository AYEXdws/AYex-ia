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
  const personaFocus = intelBrief?.persona_focus || null;
  const decisionHistory = Array.isArray(intelBrief?.decision_history) ? intelBrief.decision_history : [];
  return (
    <motion.aside
      className="glass-card h-full w-full p-5 md:p-6"
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: 0.15 }}
    >
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="section-kicker">Runtime</div>
          <h3 className="panel-title mt-2 text-2xl text-[var(--text)]">Akis</h3>
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
        <div className="mb-2 text-[11px] tracking-[0.18em] text-[var(--muted)]">SERVIS</div>
        <div className="flex items-center gap-2 text-sm text-[var(--text)]">
          <Dot active={ready} color={ready ? '#b48a61' : '#6c736f'} />
          {ready ? 'Hazir' : 'Baslatiliyor'}
        </div>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
          Feed, hafiza ve karar katmani burada ayni omurgada bulusur.
        </p>
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">BUGUN</div>
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
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">KARAR PANOSU</div>
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
          {marketFocus?.macro?.metrics ? <MacroMetricsCard metrics={marketFocus.macro.metrics} /> : null}
        </div>
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">PROFIL</div>
        <DecisionCard
          label={personaFocus?.assistant_name || 'AYEX'}
          summary={`Geri bildirim tonu: ${personaFocus?.feedback_style || 'net'}. Son cevap modu: ${insight?.response_mode || status?.mode || 'normal'}.`}
          reasons={[
            personaFocus?.focus_projects?.length ? `Odak projeler: ${personaFocus.focus_projects.join(', ')}` : '',
            personaFocus?.preferred_categories?.length ? `Onceledigi alanlar: ${personaFocus.preferred_categories.join(', ')}` : '',
          ].filter(Boolean)}
        />
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">ASSET SINYALLERI</div>
        <SignalGroup label="Kripto" rows={marketFocus?.crypto_signals} />
        <SignalGroup label="Hisse" rows={marketFocus?.equities_signals} />
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">SON KARARLAR</div>
        {decisionHistory.length ? (
          <div className="space-y-3">
            {decisionHistory.slice(0, 4).map((row, index) => (
              <DecisionHistoryRow key={`${row.session_id}-${row.timestamp}-${index}`} row={row} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3 text-sm text-[var(--muted)]">
            Karar gecmisi henuz birikmedi.
          </div>
        )}
      </div>

      <div className="mt-4 rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)]/70 p-4">
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">ALAN ODAKLARI</div>
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
        <div className="mb-3 text-[11px] tracking-[0.18em] text-[var(--muted)]">SON CEVAP IZLERI</div>
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
          {freshness} · {count}/24h
        </div>
      </div>
      <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{summary}</div>
    </div>
  );
}

function DecisionHistoryRow({ row }) {
  const title = row?.asset ? `${row.asset} · ${row.stance || 'watch'}` : row?.stance || 'karar';
  const summary = row?.summary || 'Karar ozeti yok.';
  const reasons = Array.isArray(row?.reasons) ? row.reasons.slice(0, 1) : [];
  const session = row?.session_title || 'Oturum';
  const age = row?.age_label || 'unknown';
  const status = row?.outcome_status || row?.status || 'unknown';
  const ageStatus = row?.age_status || 'unknown';
  const outcomeNote = row?.outcome_note || '';
  return (
    <div className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-[var(--text)]">{title}</div>
        <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">{session}</div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">
        <span>{status}</span>
        <span>{ageStatus} · {age}</span>
      </div>
      <div className="mt-2 text-sm leading-6 text-[var(--text)]">{summary}</div>
      {reasons.length ? <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{reasons[0]}</div> : null}
      {outcomeNote ? <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{outcomeNote}</div> : null}
    </div>
  );
}

function MacroMetricsCard({ metrics }) {
  const cells = [
    ['USD/TRY', metrics?.usdtry],
    ['XAU/USD', metrics?.xauusd],
    ['Brent', metrics?.brent],
    ['US 10Y', metrics?.us10y],
    ['Risk', metrics?.risk_mode],
  ].filter(([, value]) => value);

  if (!cells.length) return null;

  return (
    <div className="rounded-xl border border-[var(--line)] bg-white/[0.02] px-3 py-3">
      <div className="mb-2 text-[11px] uppercase tracking-[0.14em] text-[var(--accent-strong)]">Makro sinyaller</div>
      <div className="grid grid-cols-2 gap-2">
        {cells.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-[var(--line)] bg-black/10 px-3 py-2">
            <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">{label}</div>
            <div className="mt-1 text-sm font-medium text-[var(--text)]">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
