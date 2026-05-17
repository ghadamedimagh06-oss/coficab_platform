module.exports = {
  content: [
    './app/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#06b6d4',
          light: '#cffafe',
          dark: '#0e7490'
        }
      }
    }
  },
  plugins: []
};
