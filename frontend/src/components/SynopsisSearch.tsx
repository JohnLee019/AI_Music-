import { useState } from "react";

interface Props {
  onSearch: (text: string) => void;
  loading: boolean;
  // 활성 권역명(설정 시 검색이 그 권역 안으로 한정됨). null이면 전체 검색.
  scopeLabel?: string | null;
  onClearScope?: () => void;
}

const EXAMPLES = [
  "장엄하고 의례적인 궁중 분위기",
  "고요하고 명상적인 산조 같은 음악",
  "신나고 활기찬 시장 축제 느낌",
  "애절한 남도 정서의 슬픈 노래",
];

export default function SynopsisSearch({ onSearch, loading, scopeLabel, onClearScope }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const v = text.trim();
    if (v && !loading) onSearch(v);
  };

  const pickExample = (ex: string) => {
    if (loading) return;
    setText(ex);
    onSearch(ex);
  };

  return (
    <section>
      <h2 className="text-sm font-medium text-stone-500 mb-3 tracking-widest uppercase">
        시놉시스·무드로 찾기
      </h2>

      {/* 권역 한정 표시 — 소리 지도에서 권역을 고르면 그 안에서만 검색 */}
      {scopeLabel && (
        <div className="mb-2 flex items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 rounded-full bg-jade/10 text-jade px-2.5 py-1 font-medium">
            📍 {scopeLabel} 권역 안에서 검색
          </span>
          {onClearScope && (
            <button
              onClick={onClearScope}
              disabled={loading}
              className="text-stone-400 underline underline-offset-2 hover:text-stone-600 disabled:opacity-50"
            >
              전체에서 찾기
            </button>
          )}
        </div>
      )}

      <div className="card">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            // Ctrl/⌘ + Enter 로 검색
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
          }}
          rows={3}
          placeholder="영상 기획·분위기를 자유롭게 적어보세요. 예) 비 내리는 한옥에서 차를 마시는 고요한 장면…"
          className="w-full resize-none px-3 py-2 text-sm rounded-lg border border-stone-200 bg-white
                     focus:outline-none focus:ring-2 focus:ring-jade/40 focus:border-jade
                     placeholder:text-stone-400 transition-colors"
        />

        <div className="flex items-center justify-between mt-2 gap-2 flex-wrap">
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                disabled={loading}
                onClick={() => pickExample(ex)}
                className="px-2.5 py-1 text-xs rounded-full border border-stone-200 text-stone-500
                           hover:border-jade hover:text-jade transition-colors disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>

          <button
            onClick={submit}
            disabled={loading || !text.trim()}
            className="btn-primary text-sm px-5 py-1.5 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "분석 중…" : "🔍 매칭"}
          </button>
        </div>

        <p className="mt-2 text-xs text-stone-400">
          {scopeLabel
            ? `AI가 ${scopeLabel} 권역 안에서 무드에 맞는 곡을 찾습니다.`
            : "AI가 사용자가 원하는 곡을 찾습니다. (지역·유형 대신 의미 위주)"}
        </p>
      </div>
    </section>
  );
}
