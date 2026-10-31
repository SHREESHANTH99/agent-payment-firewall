/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: 'var(--paper)',
          low: 'var(--paper-low)',
          high: 'var(--paper-high)',
          highest: 'var(--paper-highest)',
        },
        ink: {
          DEFAULT: 'var(--ink)',
          muted: 'var(--ink-muted)',
        },
        vermilion: {
          DEFAULT: 'var(--vermilion)',
        },
        forest: {
          DEFAULT: 'var(--green)',
        },
        amber: {
          DEFAULT: 'var(--amber)',
        },
        border: 'var(--border-line)',
        background: 'var(--paper)',
        foreground: 'var(--ink)',
        card: {
          DEFAULT: 'var(--paper-low)',
          foreground: 'var(--ink)',
        },
        muted: {
          DEFAULT: 'var(--paper-high)',
          foreground: 'var(--ink-muted)',
        },
        accent: {
          DEFAULT: 'var(--vermilion)',
          foreground: '#FFFFFF',
        },
        status: {
          approved: '#1F7A4D',
          escalated: '#B7791F',
          denied: '#E5391B',
          executing: '#2563EB',
          failed: '#E5391B',
          frozen: '#E5391B',
          neutral: '#5C403A',
        },
      },
      fontFamily: {
        serif: ['var(--font-serif)', 'Newsreader', 'Georgia', 'serif'],
        sans: ['var(--font-ibm-sans)', 'IBM Plex Sans', '-apple-system', 'sans-serif'],
        mono: ['var(--font-ibm-mono)', 'JetBrains Mono', 'IBM Plex Mono', 'monospace'],
      },
      borderRadius: {
        none: '0px',
        sm: '2px',
        DEFAULT: '3px',
        md: '4px',
        lg: '4px',
      },
      fontSize: {
        '2xs': ['11px', { lineHeight: '14px' }],
        xs: ['13px', { lineHeight: '18px' }], // Minimum text size 13px per constraint
        sm: ['14px', { lineHeight: '20px' }],
        base: ['15px', { lineHeight: '22px' }],
        lg: ['18px', { lineHeight: '26px' }],
        xl: ['20px', { lineHeight: '28px' }],
        '2xl': ['24px', { lineHeight: '32px' }],
        '3xl': ['32px', { lineHeight: '38px' }],
        '4xl': ['40px', { lineHeight: '46px' }],
        '5xl': ['52px', { lineHeight: '58px' }],
      },
    },
  },
  plugins: [],
}
