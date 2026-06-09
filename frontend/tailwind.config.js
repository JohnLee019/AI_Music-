/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ivory: "#FBF8F2",      // 페이지 기본 배경
        paper: "#F4EEE3",      // 보조 표면 / 인셋
        hanji: "#f5f0e8",      // (구) 종이색 — 호환 유지
        ink: "#14110D",        // 텍스트 · 히어로 배경 (깊고 따뜻한 먹색)
        jade: "#1F4D3A",       // 주조색 — 깊은 청자 녹색
        gold: "#A6824C",       // 금박 — 헤어라인 · 레이블 · 강조
        "gold-light": "#C9A86A",
        persimmon: "#B24A28",  // 드물게 쓰는 따뜻한 강조(재생 상태)
      },
      fontFamily: {
        korean: ["'Noto Sans KR'", "sans-serif"],
        serif: ["'Noto Serif KR'", "serif"],
      },
      boxShadow: {
        luxe: "0 1px 2px rgba(20,17,13,.04), 0 12px 32px -12px rgba(20,17,13,.12)",
        "luxe-lg": "0 2px 4px rgba(20,17,13,.05), 0 24px 48px -16px rgba(20,17,13,.18)",
      },
    },
  },
  plugins: [],
};
