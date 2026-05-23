/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "#0f172a",
          panel: "#1e293b",
          inset: "#0b1224",
        },
        accent: {
          DEFAULT: "#38bdf8",
          soft: "#0ea5e9",
        },
      },
    },
  },
  plugins: [],
};
