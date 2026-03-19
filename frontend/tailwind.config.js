/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ayex: {
          black: '#0B0B0F',
          slate: '#111827',
          cyan: '#00F0FF',
          violet: '#8B5CF6'
        }
      },
      boxShadow: {
        neon: '0 0 0 1px rgba(0,240,255,.35), 0 0 32px rgba(0,240,255,.2)',
        violet: '0 0 0 1px rgba(139,92,246,.45), 0 0 30px rgba(139,92,246,.25)'
      },
      backdropBlur: {
        glass: '18px'
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI']
      }
    }
  },
  plugins: []
};
