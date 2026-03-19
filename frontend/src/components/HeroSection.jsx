import { motion } from 'framer-motion';
import BackgroundFX from './BackgroundFX';
import SignatureLogo from './SignatureLogo';

export default function HeroSection({ onEnter }) {
  return (
    <motion.section
      className="relative flex h-full w-full items-center justify-center px-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 1.03 }}
      transition={{ duration: 0.55 }}
    >
      <BackgroundFX />
      <div className="relative z-10 mx-auto flex max-w-4xl flex-col items-center text-center">
        <motion.p
          className="mb-5 rounded-full border border-cyan-300/30 bg-white/5 px-4 py-1 text-xs tracking-[0.35em] text-cyan-200"
          initial={{ y: 18, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          PRIVATE INTELLIGENCE SYSTEM
        </motion.p>

        <motion.h1
          className="text-6xl font-black tracking-tight md:text-8xl"
          initial={{ y: 22, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.32, duration: 0.7 }}
        >
          <span className="bg-gradient-to-r from-cyan-300 to-violet-300 bg-clip-text text-transparent">AYEX IA</span>
        </motion.h1>

        <motion.p
          className="mt-4 max-w-xl text-base text-slate-300 md:text-xl"
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.45 }}
        >
          Your private intelligent system
        </motion.p>

        <motion.div
          className="mt-10"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
        >
          <SignatureLogo />
        </motion.div>

        <motion.button
          onClick={onEnter}
          className="group mt-12 rounded-2xl border border-cyan-300/50 bg-white/5 px-8 py-3 text-sm font-semibold tracking-[0.16em] text-cyan-100 transition-all duration-300 hover:scale-[1.03] hover:border-cyan-200 hover:bg-cyan-400/10 hover:shadow-neon"
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.72 }}
          whileTap={{ scale: 0.98 }}
        >
          ENTER SYSTEM
        </motion.button>
      </div>
    </motion.section>
  );
}
