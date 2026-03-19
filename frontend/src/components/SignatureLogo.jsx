import { motion } from 'framer-motion';

export default function SignatureLogo() {
  return (
    <motion.svg
      width="260"
      height="80"
      viewBox="0 0 260 80"
      fill="none"
      className="drop-shadow-[0_0_18px_rgba(0,240,255,.35)]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
    >
      <motion.path
        d="M8 57C26 26 47 69 64 33C71 18 83 16 90 34C96 49 110 48 122 22C129 7 144 5 151 22C158 39 164 52 176 38C190 22 204 19 214 31C223 41 233 44 252 20"
        stroke="url(#ayexGrad)"
        strokeWidth="4"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 2, ease: 'easeInOut' }}
      />
      <defs>
        <linearGradient id="ayexGrad" x1="8" y1="40" x2="252" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#00F0FF" />
          <stop offset="1" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>
    </motion.svg>
  );
}
