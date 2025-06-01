/** @type {import('tailwindcss').Config} */
const defaultTheme = require('tailwindcss/defaultTheme'); // Import defaultTheme

module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",  // This includes all JavaScript/TypeScript files in your src directory
  ],
  theme: {
    extend: {
      fontFamily: { // Add fontFamily
        sans: ['"JetBrains Mono"', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        'soda-red': '#FF3B30',
        'soda-blue': '#007AFF',
        'soda-white': '#FFFFFF',
        'soda-black': '#000000',
        'soda-gray': '#1C1C1E', // A dark gray for secondary elements
      },
      animation: {
        'star-movement-bottom': 'star-movement-bottom linear infinite alternate',
        'star-movement-top': 'star-movement-top linear infinite alternate',
      },
      keyframes: {
        'star-movement-bottom': {
          '0%': { transform: 'translate(0%, 0%)', opacity: '1' },
          '100%': { transform: 'translate(-100%, 0%)', opacity: '0' },
        },
        'star-movement-top': {
          '0%': { transform: 'translate(0%, 0%)', opacity: '1' },
          '100%': { transform: 'translate(100%, 0%)', opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
