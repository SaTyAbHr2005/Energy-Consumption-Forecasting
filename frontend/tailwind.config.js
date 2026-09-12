/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#10221f",
        muted: "#71807c",
        line: "#e4ece8",
        paper: "#f7faf8",
        green: "#138a68",
        blue: "#2878c8",
        amber: "#e39a29",
        red: "#d95b55",
        brand: {
          dark: "#103d35",
          accent: "#2fb582"
        }
      },
    },
  },
  plugins: [],
}
