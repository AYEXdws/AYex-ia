import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import BackgroundFX from '../components/BackgroundFX';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function PublicPage({ onNavigateIA }) {
  const [surface, setSurface] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadSurface = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/public/intel`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || 'Public feed yuklenemedi');
      }
      setSurface(data || null);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSurface();
  }, [loadSurface]);

  useEffect(() => {
    const timer = window.setInterval(loadSurface, 60000);
    return () => window.clearInterval(timer);
  }, [loadSurface]);

  const sections = useMemo(() => Array.isArray(surface?.sections) ? surface.sections : [], [surface]);
  const pulse = useMemo(() => Array.isArray(surface?.pulse) ? surface.pulse : [], [surface]);
  const changedToday = useMemo(() => Array.isArray(surface?.changed_today) ? surface.changed_today : [], [surface]);
  const stats = surface?.overview?.stats || {};

  return (
    <motion.main
      className="relative min-h-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.45 }}
    >
      <BackgroundFX variant="public" />

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-4 px-4 pb-6 pt-4 md:px-6 md:pb-8 md:pt-6">
        <header className="public-shell flex flex-col gap-4 px-5 py-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-full border border-[var(--line)] bg-black/20 px-3 py-1 text-[11px] tracking-[0.18em] text-[var(--muted)]">
              AYEXDWS
            </div>
            <div className="text-sm text-[var(--muted)]">Canli akislar ve secilmis sinyaller</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <NavPill active>Feed</NavPill>
            <button type="button" onClick={onNavigateIA} className="nav-pill">
              IA
            </button>
            <div className="rounded-full border border-[var(--line)] bg-black/15 px-3 py-2 text-[11px] tracking-[0.12em] text-[var(--muted)]">
              Son guncelleme: {formatTimestamp(surface?.updated_at)}
            </div>
          </div>
        </header>

        <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <motion.div
            className="public-hero"
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.08 }}
          >
            <div className="section-kicker">Yayin Yuzeyi</div>
            <h1 className="public-title mt-3">
              {surface?.overview?.headline || 'Bes akis tek sayfada toplanir.'}
            </h1>
            <p className="public-copy mt-4 max-w-3xl">
              {surface?.overview?.summary ||
                'Gun icinde degisen piyasa, makro, siber ve dunya sinyalleri ayni omurgadan okunur.'}
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              <MetricCard label="Aktif akis" value={stats.active_feeds ?? '-'} />
              <MetricCard label="Yayinda event" value={stats.published_events ?? '-'} />
              <MetricCard label="Agirlik merkezi" value={stats.lead_domain || '-'} />
            </div>

            <div className="mt-8 flex flex-wrap gap-2">
              {pulse.map((item) => (
                <div key={item.label} className="signal-pill">
                  <span>{item.label}</span>
                  <strong>{item.summary}</strong>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.aside
            className="public-panel"
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.14 }}
          >
            <div className="section-kicker">Akis Ozeti</div>
            <div className="mt-4 space-y-3">
              {sections.map((section) => (
                <div key={section.key} className="rounded-[22px] border border-[var(--line)] bg-white/[0.03] px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-[15px] font-semibold text-[var(--text)]">{section.label}</div>
                    <div className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[10px] tracking-[0.14em] text-[var(--muted)]">
                      {section.freshness} · {section.count_24h}/24h
                    </div>
                  </div>
                  <div className="mt-3 text-sm leading-6 text-[var(--text)]">{section.summary}</div>
                </div>
              ))}
            </div>
          </motion.aside>
        </section>

        {error ? (
          <div className="public-shell border-[var(--danger)] px-5 py-4 text-sm text-[var(--danger)]">
            {error}
          </div>
        ) : null}

        <section className="public-shell px-5 py-5">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <div className="section-kicker">Bugun Degisenler</div>
              <h2 className="panel-title mt-2 text-3xl text-[var(--text)]">Bugunun secilmis akisi</h2>
            </div>
            <div className="text-sm text-[var(--muted)]">Ayni omurgadan secilen son degisimler</div>
          </div>
          <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
            {changedToday.length ? (
              changedToday.map((item) => (
                <div key={`${item.section}-${item.title}`} className="feed-item">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--accent-strong)]">{item.section}</div>
                    <div className="text-[11px] tracking-[0.12em] text-[var(--muted)]">{formatTimestamp(item.timestamp)}</div>
                  </div>
                  <div className="mt-3 text-sm font-semibold leading-6 text-[var(--text)]">{item.title}</div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.12em] text-[var(--muted)]">
                    <span>{item.source}</span>
                    <span>score {formatScore(item.score)}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="feed-item text-sm text-[var(--muted)]">Yayinlanacak degisim henuz secilmedi.</div>
            )}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {sections.map((section, index) => (
            <motion.article
              key={section.key}
              className={`feed-card ${index === 0 ? 'xl:col-span-2' : ''}`}
              initial={{ y: 26, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.18 + index * 0.06 }}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="section-kicker">{section.label}</div>
                  <h2 className="mt-3 text-[1.9rem] leading-none text-[var(--text)] md:text-[2.3rem]">
                    {section.headline}
                  </h2>
                </div>
                <div className={`feed-state feed-state-${section.freshness_state || 'unknown'}`}>{section.signal || section.freshness_state || 'unknown'}</div>
              </div>

              <p className="mt-4 max-w-3xl text-sm leading-7 text-[var(--muted)]">{section.summary}</p>

              {section.reasons?.length ? (
                <div className="mt-5 flex flex-wrap gap-2">
                  {section.reasons.map((reason) => (
                    <div key={reason} className="rounded-full border border-[var(--line)] bg-black/10 px-3 py-2 text-xs text-[var(--muted)]">
                      {reason}
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="mt-6 grid gap-3">
                {section.items?.length ? (
                  section.items.map((item) => (
                    <div key={item.id || `${section.key}-${item.title}`} className="feed-item">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <div className="text-[15px] font-semibold text-[var(--text)]">{item.title}</div>
                          <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{item.summary}</div>
                        </div>
                        <div className="shrink-0 text-right">
                          <div className="text-[11px] tracking-[0.14em] text-[var(--muted)]">{formatTimestamp(item.timestamp)}</div>
                          <div className="mt-2 text-[11px] uppercase tracking-[0.14em] text-[var(--accent-strong)]">
                            {item.source}
                          </div>
                        </div>
                      </div>
                      {item.tags?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {item.tags.map((tag) => (
                            <span key={`${item.id}-${tag}`} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <div className="feed-item text-sm text-[var(--muted)]">
                    {loading ? 'Akis yukleniyor...' : 'Bu akis icin yayinlanacak event yok.'}
                  </div>
                )}
              </div>
            </motion.article>
          ))}
        </section>
      </div>
    </motion.main>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="metric-card">
      <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">{label}</div>
      <div className="mt-3 text-3xl font-semibold text-[var(--text)]">{value}</div>
    </div>
  );
}

function NavPill({ active, children }) {
  return <div className={`nav-pill ${active ? 'nav-pill-active' : ''}`}>{children}</div>;
}

function formatTimestamp(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('tr-TR', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatScore(value) {
  const score = Number(value);
  if (!Number.isFinite(score)) return '-';
  return score.toFixed(2);
}
