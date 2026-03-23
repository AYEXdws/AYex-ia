import { useMemo } from 'react';
import { motion } from 'framer-motion';

export default function BackgroundFX() {
  const particles = useMemo(
    () => Array.from({ length: 8 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      delay: Math.random() * 3,
      duration: 12 + Math.random() * 10
    })),
    []
  );

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_14%_18%,rgba(180,138,97,.18),transparent_26%),radial-gradient(circle_at_88%_12%,rgba(113,128,109,.15),transparent_24%),radial-gradient(circle_at_50%_110%,rgba(255,255,255,.05),transparent_40%)]" />
      <motion.div
        className="absolute inset-0 opacity-40"
        animate={{ backgroundPosition: ['0% 0%', '100% 60%'] }}
        transition={{ repeat: Infinity, duration: 32, ease: 'linear' }}
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px)',
          backgroundSize: '64px 64px'
        }}
      />
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className="absolute h-24 w-24 rounded-full bg-[radial-gradient(circle,rgba(180,138,97,.12),transparent_70%)] blur-xl"
          style={{ left: `${p.x}%`, top: `${p.y}%` }}
          animate={{ y: [-18, 14, -18], opacity: [0.18, 0.34, 0.18] }}
          transition={{ delay: p.delay, duration: p.duration, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}
