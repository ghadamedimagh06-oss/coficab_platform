const { palette } = require('./lib/theme');

module.exports = {
  // Dark mode follows the OS preference. NOTE: the color tokens below resolve
  // to literal light-palette hexes at build time, so flipping the OS to dark
  // does not yet recolor the `bg-canvas`/`border-border`/`text-muted`/`bg-surface`
  // utilities. To actually activate dark mode with zero churn later, point those
  // four tokens at their CSS vars (e.g. canvas: 'var(--color-canvas)') — the dark
  // overrides for those vars already live in globals.css.
  darkMode: 'media',
  content: [
    './app/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        // Violet-first brand system — single source in lib/theme.js.
        brand: palette.brand,
        canvas: palette.canvas,
        surface: palette.surface,
        border: palette.border,
        muted: palette.muted,
        ink: palette.ink,
        success: palette.success,
        danger: palette.danger,
        warning: palette.warning,
        // Semantic aliases.
        primary: palette.brand[600],
        ring: palette.brand[400]
      }
    }
  },
  plugins: []
};
