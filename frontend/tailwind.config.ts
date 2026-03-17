import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          accent: "#E6D18C", // Yellow/Gold from Figma
          dark: "#000000",
          card: "#0D1117",
          border: "#FFFFFF"
        },
      },
      boxShadow: {
        neo: "4px 4px 0px 0px rgba(0,0,0,1)",
        "neo-sm": "2px 2px 0px 0px rgba(0,0,0,1)",
        "neo-lg": "8px 8px 0px 0px rgba(0,0,0,1)",
        "neo-white": "4px 4px 0px 0px rgba(255,255,255,1)",
      },
      fontFamily: {
        sans: ["var(--font-public-sans)", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;