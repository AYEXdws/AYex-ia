import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import BackgroundFX from '../components/BackgroundFX';
import ChatPanel from '../components/ChatPanel';
import SessionRail from '../components/SessionRail';
import StatusPanel from '../components/StatusPanel';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function SystemPage({ onNavigateHome }) {
  const [token, setToken] = useState(localStorage.getItem('ayex_token') || '');
  const [status, setStatus] = useState({
    model: '-',
    latency: '-',
    mode: '-',
    source: '-',
    ready: false
  });
  const [auth, setAuth] = useState({ username: '', password: '', error: '', loading: false });
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [intelBrief, setIntelBrief] = useState(null);
  const [insight, setInsight] = useState(null);

  async function login(e) {
    e.preventDefault();
    setAuth((s) => ({ ...s, error: '', loading: true }));
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: auth.username, password: auth.password })
      });
      const data = await res.json();
      if (!res.ok || !data.access_token) {
        throw new Error(data?.detail || 'Login failed');
      }
      localStorage.setItem('ayex_token', data.access_token);
      setToken(data.access_token);
      setStatus((s) => ({ ...s, ready: true }));
    } catch (err) {
      setAuth((s) => ({ ...s, error: err.message }));
    } finally {
      setAuth((s) => ({ ...s, loading: false }));
    }
  }

  function logout() {
    localStorage.removeItem('ayex_token');
    setToken('');
    setStatus({ model: '-', latency: '-', mode: '-', source: '-', ready: false });
    setSessions([]);
    setSelectedSessionId('');
    setIntelBrief(null);
    setInsight(null);
  }

  const fetchAuthed = useCallback(
    async (path) => {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || 'Request failed');
      }
      return data;
    },
    [token]
  );

  const loadSurface = useCallback(async () => {
    if (!token) return;
    try {
      const [sessionData, intelData] = await Promise.all([
        fetchAuthed('/sessions?limit=24'),
        fetchAuthed('/intel')
      ]);
      const nextSessions = Array.isArray(sessionData?.sessions) ? sessionData.sessions : [];
      setSessions(nextSessions);
      setIntelBrief(intelData || null);
      setSelectedSessionId((current) => {
        if (current && nextSessions.some((item) => item.id === current)) {
          return current;
        }
        return nextSessions[0]?.id || '';
      });
    } catch (err) {
      setStatus((prev) => ({ ...prev, ready: true, source: 'surface_error' }));
    }
  }, [fetchAuthed, token]);

  useEffect(() => {
    loadSurface();
  }, [loadSurface]);

  useEffect(() => {
    if (!token) return undefined;
    const timer = window.setInterval(() => {
      loadSurface();
    }, 90000);
    return () => window.clearInterval(timer);
  }, [loadSurface, token]);

  return (
    <motion.main
      className="relative h-full w-full"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.45 }}
    >
      <BackgroundFX variant="desk" />

      <div className="relative z-10 mx-auto flex h-full w-full max-w-[1500px] flex-col gap-4 p-4 md:p-6">
        <header className="glass-card flex flex-col gap-4 px-5 py-5 md:flex-row md:items-end md:justify-between md:px-7">
          <div className="max-w-2xl">
            <div className="section-kicker">AYEX / Desk</div>
            <h1 className="panel-title mt-2 text-3xl text-[var(--text)] md:text-[2.4rem]">Calisma Masasi</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--muted)]">
              Oturumlar, canli akislar ve kararlar burada toplanir. Yayin yuzeyi ana sayfada kalir, calisma akisi
              burada devam eder.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 md:justify-end">
            <button type="button" onClick={onNavigateHome} className="nav-pill">
              Feed
            </button>
            <div className="nav-pill nav-pill-active">IA</div>
          </div>
        </header>

        {!token ? (
          <section className="glass-card mx-auto mt-8 w-full max-w-md p-6 md:p-7">
            <div className="section-kicker">Giris</div>
            <h2 className="panel-title mb-3 mt-2 text-2xl text-[var(--text)]">Desk erisimi</h2>
            <p className="mb-5 text-sm leading-6 text-[var(--muted)]">
              Giris sonrasi oturumlar, canli akis ve karar katmani birlikte acilir.
            </p>
            <form onSubmit={login} className="space-y-3">
              <input
                value={auth.username}
                onChange={(e) => setAuth((s) => ({ ...s, username: e.target.value }))}
                placeholder="Username"
                className="soft-input h-12 px-4 text-sm"
              />
              <input
                type="password"
                value={auth.password}
                onChange={(e) => setAuth((s) => ({ ...s, password: e.target.value }))}
                placeholder="Password"
                className="soft-input h-12 px-4 text-sm"
              />
              {auth.error ? <p className="text-xs text-[var(--danger)]">{auth.error}</p> : null}
              <button
                type="submit"
                disabled={auth.loading}
                className="soft-button h-12 w-full rounded-2xl text-xs tracking-[0.16em]"
              >
                {auth.loading ? 'KONTROL EDILIYOR' : 'DESK AC'}
              </button>
            </form>
          </section>
        ) : (
          <>
            <section className="glass-card flex flex-wrap items-stretch gap-3 px-4 py-4">
              <PulseCell label="Kripto" value={intelBrief?.live_inventory?.feeds?.crypto?.freshness} detail={intelBrief?.market_focus?.crypto?.summary} />
              <PulseCell label="Hisse" value={intelBrief?.live_inventory?.feeds?.equities?.freshness} detail={intelBrief?.market_focus?.equities?.summary} />
              <PulseCell label="Makro" value={intelBrief?.live_inventory?.feeds?.macro?.freshness} detail={intelBrief?.market_focus?.macro?.summary} />
              <PulseCell label="World" value={intelBrief?.live_inventory?.feeds?.world?.freshness} detail={intelBrief?.domain_focus?.world?.summary} />
              <PulseCell label="Cyber" value={intelBrief?.live_inventory?.feeds?.cyber?.freshness} detail={intelBrief?.domain_focus?.cyber?.summary} />
            </section>

            <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[280px_minmax(0,1fr)_340px]">
              <SessionRail
                sessions={sessions}
                selectedSessionId={selectedSessionId}
                onSelectSession={setSelectedSessionId}
                onNewSession={() => setSelectedSessionId('')}
              />
              <ChatPanel
                token={token}
                selectedSessionId={selectedSessionId}
                onSessionChange={setSelectedSessionId}
                onStatus={setStatus}
                onRefreshSurface={loadSurface}
                onInsight={setInsight}
              />
              <StatusPanel status={status} intelBrief={intelBrief} insight={insight} onLogout={logout} />
            </section>
          </>
        )}
      </div>
    </motion.main>
  );
}

function PulseCell({ label, value, detail }) {
  return (
    <div className="min-w-[180px] flex-1 rounded-[22px] border border-[var(--line)] bg-white/[0.03] px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">{label}</div>
        <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--accent-strong)]">{value || 'unknown'}</div>
      </div>
      <div className="mt-2 text-sm leading-6 text-[var(--text)]">{detail || 'Sinyal yok.'}</div>
    </div>
  );
}
