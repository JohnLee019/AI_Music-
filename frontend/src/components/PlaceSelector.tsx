import { useEffect, useState } from "react";
import type { Place } from "../api";
import { fetchPlaceSuggestions } from "../api";

interface Props {
  places: Place[];
  selected: Place | null;
  onSelect: (place: Place) => void;
  loading: boolean;
  collapsed?: boolean;       // 장소 선택 후 목록을 접어 결과로 바로 이동
  onExpand?: () => void;     // 다른 장소 선택을 위해 다시 펼치기
}

const TYPE_ICON: Record<string, string> = {
  궁궐: "🏯",
  민속마을: "🏘️",
  한옥마을: "🏠",
  전통시장: "🏪",
};

const FALLBACK_IMAGE: Record<string, string> = {
  궁궐: "https://images.unsplash.com/photo-1547826039-bfc35e0f1ea8?auto=format&fit=crop&w=600&q=80",
  사찰: "https://images.unsplash.com/photo-160162161407e-12f0b9ca0448?auto=format&fit=crop&w=600&q=80",
  한옥마을: "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=600&q=80",
  민속마을: "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=600&q=80",
  서원: "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=600&q=80",
  전통시장: "https://images.unsplash.com/photo-1583212292454-1fe6229603b7?auto=format&fit=crop&w=600&q=80",
};

const getPlaceImage = (place: Place) => {
  if (place.image_url) return place.image_url;
  return FALLBACK_IMAGE[place.type] || "https://images.unsplash.com/photo-1608976478546-d249d375369f?auto=format&fit=crop&w=600&q=80";
};

export default function PlaceSelector({ places, selected, onSelect, loading, collapsed = false, onExpand }: Props) {
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

  // 검색 결과가 없을 때 의미가 가까운 보유 장소를 추천 (디바운스).
  const [suggestions, setSuggestions] = useState<Place[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const noLocalMatch = filtered.length === 0;
  const query = search.trim();

  useEffect(() => {
    if (query.length < 2 || !noLocalMatch) {
      setSuggestions([]);
      return;
    }
    setSuggesting(true);
    const handle = setTimeout(() => {
      fetchPlaceSuggestions(query)
        .then(setSuggestions)
        .catch(() => setSuggestions([]))
        .finally(() => setSuggesting(false));
    }, 400);
    return () => clearTimeout(handle);
  }, [query, noLocalMatch]);

  // 접힌 상태: 선택한 장소만 간단히 보여주고 '다른 장소 선택' 버튼 제공 (스크롤 최소화)
  if (collapsed && selected) {
    return (
      <section>
        <div className="flex items-center gap-3 card">
          <span className="text-2xl">{TYPE_ICON[selected.type] ?? "📍"}</span>
          <div className="min-w-0">
            <div className="text-xs text-stone-400">선택한 장소</div>
            <div className="font-semibold leading-tight truncate">{selected.name}</div>
            <div className="text-xs text-stone-500">{selected.type} · {selected.region}</div>
          </div>
          <button
            className="ml-auto text-xs px-3 py-1.5 rounded-lg border border-stone-200 text-stone-600
                       hover:border-jade hover:text-jade transition-colors disabled:opacity-50"
            onClick={onExpand}
            disabled={loading}
          >
            다른 장소 선택
          </button>
        </div>
      </section>
    );
  }

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
                className={`card text-left transition-all hover:-translate-y-0.5 active:scale-95 overflow-hidden
                  ${isSelected ? "ring-2 ring-jade bg-jade/5 border-jade" : "hover:border-stone-300"}
                  ${loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <div className="relative -mx-5 -mt-5 mb-3 h-24 overflow-hidden rounded-t-2xl bg-stone-100">
                  <img
                    src={getPlaceImage(place)}
                    alt={place.name}
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute top-2 left-2 bg-white/80 backdrop-blur-sm rounded-full w-7 h-7 flex items-center justify-center text-sm shadow-sm">
                    {TYPE_ICON[place.type] ?? "📍"}
                  </span>
                </div>
                <div className="font-semibold text-base leading-tight">{place.name}</div>
                <div className="text-xs text-stone-500 mt-0.5">{place.type}</div>
                <div className="text-xs text-stone-400 mt-0.5 truncate">{place.region}</div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="py-8 text-center text-sm text-stone-400 rounded-xl border border-dashed border-stone-200 px-4">
          <div className="text-2xl mb-2">🔍</div>
          <p>
            {typeFilter && search
              ? `"${search}" · ${typeFilter}`
              : typeFilter
              ? typeFilter
              : `"${search}"`}
            에 맞는 장소가 없습니다.
          </p>

          {/* 의미 기반 연관 장소 추천 */}
          {query.length >= 2 && !typeFilter && (
            <div className="mt-4">
              {suggesting && suggestions.length === 0 ? (
                <p className="text-xs text-stone-400">비슷한 장소 찾는 중…</p>
              ) : suggestions.length > 0 ? (
                <>
                  <p className="text-xs text-stone-500 mb-2">
                    혹시 이런 장소를 찾으셨나요?
                  </p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {suggestions.map((p) => (
                      <button
                        key={p.id}
                        disabled={loading}
                        onClick={() => onSelect(p)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-stone-200
                                   bg-white text-stone-600 hover:border-jade hover:text-jade transition-colors
                                   disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span>{TYPE_ICON[p.type] ?? "📍"}</span>
                        <span className="font-medium">{p.name}</span>
                        {typeof p.similarity === "number" && (
                          <span className="text-[10px] text-stone-400">
                            {Math.round(p.similarity * 100)}%
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          )}

          {hasActiveFilter && (
            <button
              className="mt-4 block mx-auto text-xs text-jade underline underline-offset-2"
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
