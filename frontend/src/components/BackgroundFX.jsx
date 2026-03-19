import { useMemo } from 'react';
import { motion } from 'framer-motion';

export default function BackgroundFX() {
  const particles = useMemo(
    () => Array.from({ length: 26 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      delay: Math.random() * 3,
      duration: 5 + Math.random() * 7
    })),
    []
  );

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(0,240,255,.18),transparent_35%),radial-gradient(circle_at_80%_0%,rgba(139,92,246,.2),transparent_30%),radial-gradient(circle_at_50%_100%,rgba(0,150,255,.15),transparent_40%)]" />
      <motion.div
        className="absolute inset-0 opacity-30"
        animate={{ backgroundPosition: ['0% 0%', '100% 100%'] }}
        transition={{ repeat: Infinity, duration: 24, ease: 'linear' }}
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px)',
          backgroundSize: '42px 42px'
        }}
      />
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className="absolute h-1.5 w-1.5 rounded-full bg-cyan-300/80 shadow-[0_0_16px_rgba(0,240,255,.8)]"
          style={{ left: `${p.x}%`, top: `${p.y}%` }}
          animate={{ y: [-12, 12, -12], opacity: [0.3, 1, 0.3] }}
          transition={{ delay: p.delay, duration: p.duration, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}
