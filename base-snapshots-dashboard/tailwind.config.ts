import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#0052FF",
        },
        content: {
          DEFAULT: "#787878",
          subtle: "#787878",
          dark: "#c9d1d9",
          "dark-subtle": "#9aa4b2",
        },
        table: {
          DEFAULT: "#4a4a4a",
          subtle: "#5f5f5f",
          dark: "#c9d1d9",
          "dark-subtle": "#9aa4b2",
        },
        link: {
          DEFAULT: "#0052FF",
          dark: "#6ea8ff",
          "dark-hover": "#9bbcff",
        },
        icon: {
          muted: "#c8c8c8",
          hover: "#787878",
          "dark-hover": "#999999",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
