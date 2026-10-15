/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        brand: { 50: '#f3f0ff', 100: '#e7e1ff', 400: '#a18bff', 500: '#7c5cfc', 600: '#6a49ec', 700: '#5a3bd1' },
      },
    },
  },
  plugins: [],
}
