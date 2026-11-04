/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark': {
          'bg': '#0f0f1e',
          'card': '#1a1a2e',
          'border': '#2d2d44',
          'text': '#e0e0e0',
          'text-muted': '#9ca3af',
        },
        'accent': {
          'purple': '#a78bfa',
          'purple-dark': '#7c3aed',
          'purple-light': '#c4b5fd',
        }
      },
      fontFamily: {
        'sans': ['Inter', 'sans-serif'],
      },
      animation: {
        'pulse-subtle': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite',
        'bounce-subtle': 'bounce-subtle 2s infinite',
      },
      keyframes: {
        glow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(167, 139, 250, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(167, 139, 250, 0.6)' },
        },
        'bounce-subtle': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        }
      }
    },
  },
  plugins: [],
}
