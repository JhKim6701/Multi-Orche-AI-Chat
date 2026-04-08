import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: '#e4e7ec',
        background: '#fcfcfd',
        card: '#ffffff',
        muted: '#f8f9fb',
        primary: '#175cd3',
      },
      borderRadius: {
        lg: '10px',
      },
    },
  },
  plugins: [],
};

export default config;
