import { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import HeroSection from './components/HeroSection';
import SystemPage from './pages/SystemPage';

export default function App() {
  const [entered, setEntered] = useState(false);

  return (
    <div className="h-screen w-screen overflow-hidden bg-ayex-black text-white">
      <AnimatePresence mode="wait">
        {entered ? (
          <SystemPage key="system" onExit={() => setEntered(false)} />
        ) : (
          <HeroSection key="hero" onEnter={() => setEntered(true)} />
        )}
      </AnimatePresence>
    </div>
  );
}
