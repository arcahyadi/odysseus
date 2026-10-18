/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./static/**/*.{html,js}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        odysseus: {
          bg:      'var(--bg)',
          fg:      'var(--fg)',
          panel:   'var(--panel)',
          border:  'var(--border)',
          red:     'var(--red)',
          green:   'var(--green)',
          warn:    'var(--warn)',
        },
        syntax: {
          bg:       'var(--hl-bg)',
          fg:       'var(--hl-fg)',
          keyword:  'var(--hl-keyword)',
          string:   'var(--hl-string)',
          comment:  'var(--hl-comment)',
          function: 'var(--hl-function)',
          number:   'var(--hl-number)',
          builtin:  'var(--hl-builtin)',
          variable: 'var(--hl-variable)',
          params:   'var(--hl-params)',
        },
        semantic: {
          error:          'var(--color-error)',
          'error-light':  'var(--color-error-light)',
          success:        'var(--color-success)',
          warning:        'var(--color-warning)',
          danger:         'var(--color-danger)',
          recording:      'var(--color-recording)',
          muted:          'var(--color-muted)',
          'muted-alt':    'var(--color-muted-alt)',
          accent:         'var(--color-accent)',
          'agent-active': 'var(--color-agent-active)',
          'brand-blue':   'var(--color-brand-blue)',
          'blind-orange': 'var(--color-blind-orange)',
          'link-hover':   'var(--color-link-hover)',
          subheader:      'var(--color-subheader)',
        },
      },
      fontFamily: {
        mono: ['Fira Code', 'monospace'],
        'open-dyslexic': ['OpenDyslexic', 'sans-serif'],
      },
      fontSize: {
        'density-compact': '13px',
        'density-spacious': '16px',
      },
      scrollbarColor: {
        thumb: 'var(--red)',
        track: 'var(--panel)',
      },
    },
  },
  plugins: [],
};
