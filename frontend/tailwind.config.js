/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#3b82f6", // 파란색
        secondary: "#10b981", // 초록색
        warning: "#f59e0b", // 주황색
        danger: "#ef4444", // 빨간색
        dark: "#1f2937", // 다크 그레이
        light: "#f9fafb", // 밝은 그레이
      },
    },
  },
  plugins: [],
};
