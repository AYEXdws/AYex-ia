import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import PublicPage from './pages/PublicPage';
import SystemPage from './pages/SystemPage';

function normalizePath(pathname) {
  return String(pathname || '').startsWith('/ia') ? '/ia' : '/';
}

export default function App() {
  const [path, setPath] = useState(() => normalizePath(window.location.pathname));

  useEffect(() => {
    function handlePopState() {
      setPath(normalizePath(window.location.pathname));
    }

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const currentView = useMemo(() => normalizePath(path), [path]);

  function navigate(nextPath) {
    const normalized = normalizePath(nextPath);
    if (normalized === currentView) return;
    window.history.pushState({}, '', normalized);
    setPath(normalized);
  }

  return (
    <div className="min-h-screen w-screen overflow-x-hidden bg-ayex-black text-white">
      <AnimatePresence mode="wait">
        {currentView === '/ia' ? (
          <SystemPage key="ia" onNavigateHome={() => navigate('/')} />
        ) : (
          <PublicPage key="public" onNavigateIA={() => navigate('/ia')} />
        )}
      </AnimatePresence>
    </div>
  );
}
