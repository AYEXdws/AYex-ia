import { useState } from 'react';
import { motion } from 'framer-motion';
import BackgroundFX from '../components/BackgroundFX';
import ChatPanel from '../components/ChatPanel';
import StatusPanel from '../components/StatusPanel';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function SystemPage() {
  const [token, setToken] = useState(localStorage.getItem('ayex_token') || '');
  const [status, setStatus] = useState({
    model: '-',
    latency: '-',
    mode: '-',
    source: '-',
    ready: false
  });
  const [auth, setAuth] = useState({ username: '', password: '', error: '', loading: false });

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
  }

  return (
    <motion.main
      className="relative h-full w-full"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.45 }}
    >
      <BackgroundFX />

      <div className="relative z-10 mx-auto flex h-full w-full max-w-[1500px] flex-col gap-4 p-4 md:p-6">
        <header className="glass-card flex items-center justify-between px-5 py-4">
          <div>
            <h1 className="text-xl font-bold tracking-[0.12em] text-cyan-100">AYEX IA</h1>
            <p className="text-xs tracking-[0.2em] text-slate-400">PRIVATE INTELLIGENT SYSTEM</p>
          </div>
          <div className="text-right text-xs text-slate-300">
            <div className="tracking-[0.18em]">Premium Command Deck</div>
            <div className="text-slate-500">Lux • Modern • Interactive</div>
          </div>
        </header>

        {!token ? (
          <section className="glass-card mx-auto mt-8 w-full max-w-md p-6">
            <h2 className="mb-4 text-lg font-semibold text-slate-100">Secure Login</h2>
            <form onSubmit={login} className="space-y-3">
              <input
                value={auth.username}
                onChange={(e) => setAuth((s) => ({ ...s, username: e.target.value }))}
                placeholder="Username"
                className="h-11 w-full rounded-xl border border-white/15 bg-black/30 px-3 text-sm outline-none focus:border-cyan-300/60"
              />
              <input
                type="password"
                value={auth.password}
                onChange={(e) => setAuth((s) => ({ ...s, password: e.target.value }))}
                placeholder="Password"
                className="h-11 w-full rounded-xl border border-white/15 bg-black/30 px-3 text-sm outline-none focus:border-cyan-300/60"
              />
              {auth.error ? <p className="text-xs text-rose-300">{auth.error}</p> : null}
              <button
                type="submit"
                disabled={auth.loading}
                className="h-11 w-full rounded-xl border border-cyan-300/50 bg-cyan-500/10 text-xs tracking-[0.16em] text-cyan-100 hover:shadow-neon disabled:opacity-50"
              >
                {auth.loading ? 'AUTHENTICATING...' : 'ENTER AYEX'}
              </button>
            </form>
          </section>
        ) : (
          <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[1fr_300px]">
            <ChatPanel token={token} onStatus={setStatus} />
            <StatusPanel status={status} onLogout={logout} />
          </section>
        )}
      </div>
    </motion.main>
  );
}
