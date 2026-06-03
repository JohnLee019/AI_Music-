/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        hanji: "#f5f0e8",
        ink: "#1a1410",
        jade: "#2d6a4f",
        persimmon: "#c7522a",
        gold: "#b8860b",
      },
      fontFamily: {
        korean: ["'Noto Sans KR'", "sans-serif"],
      },
    },
  },
  plugins: [],
};
