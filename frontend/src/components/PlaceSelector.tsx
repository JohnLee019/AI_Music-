import { useState } from "react";
import type { Place } from "../api";

interface Props {
  places: Place[];
  selected: Place | null;
  onSelect: (place: Place) => void;
  loading: boolean;
}

const TYPE_ICON: Record<string, string> = {
  궁궐: "🏯",
  민속마을: "🏘️",
  한옥마을: "🏠",
  전통시장: "🏪",
};

export default function PlaceSelector({ places, selected, onSelect, loading }: Props) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  const types = [...new Set(places.map((p) => p.type))];

  const filtered = places.filter((p) => {
    const matchesType = !typeFilter || p.type === typeFilter;
    const q = search.trim().toLowerCase();
    const matchesSearch =
      !q ||
      p.name.toLowerCase().includes(q) ||
      p.type.toLowerCase().includes(q) ||
      p.region.toLowerCase().includes(q) ||
      p.cultural_keywords.some((kw) => kw.toLowerCase().includes(q));
    return matchesType && matchesSearch;
  });

  const hasActiveFilter = search.trim() !== "" || typeFilter !== null;

  return (
    <section>
      <h2 className="text-sm font-medium text-stone-500 mb-3 tracking-widest uppercase">
        장소 선택
      </h2>

      {/* 검색 */}
      <div className="relative mb-3">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none">
          🔍
        </span>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="장소 이름, 유형, 지역, 키워드로 검색…"
          className="w-full pl-9 pr-8 py-2 text-sm rounded-lg border border-stone-200 bg-white
                     focus:outline-none focus:ring-2 focus:ring-jade/40 focus:border-jade
                     placeholder:text-stone-400 transition-colors"
        />
        {search && (
          <button
            aria-label="검색어 지우기"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600 text-lg leading-none"
            onClick={() => setSearch("")}
          >
            ×
          </button>
        )}
      </div>

      {/* 유형 필터 칩 */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <button
          onClick={() => setTypeFilter(null)}
          className={`px-3 py-1 text-xs rounded-full border transition-colors ${
            !typeFilter
              ? "bg-jade text-white border-jade"
              : "border-stone-200 text-stone-500 hover:border-jade hover:text-jade"
          }`}
        >
          전체
        </button>
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(typeFilter === t ? null : t)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${
              typeFilter === t
                ? "bg-jade text-white border-jade"
                : "border-stone-200 text-stone-500 hover:border-jade hover:text-jade"
            }`}
          >
            {TYPE_ICON[t] ?? "📍"} {t}
          </button>
        ))}
      </div>

      {/* 결과 */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-2 gap-3">
          {filtered.map((place) => {
            const isSelected = selected?.id === place.id;
            return (
              <button
                key={place.id}
                disabled={loading}
                onClick={() => onSelect(place)}
                className={`card text-left transition-all hover:-translate-y-0.5 active:scale-95
                  ${isSelected ? "ring-2 ring-jade bg-jade/5 border-jade" : "hover:border-stone-300"}
                  ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <div className="text-2xl mb-1">{TYPE_ICON[place.type] ?? "📍"}</div>
                <div className="font-semibold text-base leading-tight">{place.name}</div>
                <div className="text-xs text-stone-500 mt-0.5">{place.type}</div>
                <div className="text-xs text-stone-400 mt-0.5 truncate">{place.region}</div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="py-10 text-center text-sm text-stone-400 rounded-xl border border-dashed border-stone-200">
          <div className="text-2xl mb-2">🔍</div>
          <p>
            {typeFilter && search
              ? `"${search}" · ${typeFilter}`
              : typeFilter
              ? typeFilter
              : `"${search}"`}
            에 맞는 장소가 없습니다.
          </p>
          {hasActiveFilter && (
            <button
              className="mt-2 text-xs text-jade underline underline-offset-2"
              onClick={() => { setSearch(""); setTypeFilter(null); }}
            >
              필터 초기화
            </button>
          )}
        </div>
      )}
    </section>
  );
}
