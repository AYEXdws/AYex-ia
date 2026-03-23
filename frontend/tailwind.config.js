/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ayex: {
          ink: '#111315',
          panel: '#181d22',
          line: '#2a3138',
          mist: '#d8d2c8',
          clay: '#b48a61',
          moss: '#70806d'
        }
      },
      boxShadow: {
        panel: '0 24px 80px rgba(0, 0, 0, 0.28)',
        inset: 'inset 0 1px 0 rgba(255,255,255,0.05)'
      },
      backdropBlur: {
        glass: '18px'
      },
      fontFamily: {
        sans: ['Manrope', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI'],
        display: ['Fraunces', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace']
      }
    }
  },
  plugins: []
};
