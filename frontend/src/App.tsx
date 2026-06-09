import { useEffect, useMemo, useRef, useState } from "react";
import type { MatchResult, Place } from "./api";
import { fetchMatch, fetchMatchByRegion, fetchMatchByRegionQuery, fetchMatchByText, fetchPlaces } from "./api";
import GenerateBGM from "./components/GenerateBGM";
import PlaceSelector from "./components/PlaceSelector";
import RegionSoundMap from "./components/RegionSoundMap";
import SelectedPlaceMap from "./components/SelectedPlaceMap";
import SynopsisSearch from "./components/SynopsisSearch";
import TrackCard from "./components/TrackCard";
import { REGION_META } from "./data/regionGeo";

const FALLBACK_IMAGE: Record<string, string> = {
  궁궐: "https://images.unsplash.com/photo-1547826039-bfc35e0f1ea8?auto=format&fit=crop&w=600&q=80",
  사찰: "https://images.unsplash.com/photo-160162161407e-12f0b9ca0448?auto=format&fit=crop&w=600&q=80",
  한옥마을: "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=600&q=80",
  민속마을: "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=600&q=80",
  서원: "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=600&q=80",
  전통시장: "https://images.unsplash.com/photo-1583212292454-1fe6229603b7?auto=format&fit=crop&w=600&q=80",
};

// Set of images used across the application for the dynamic banner (using larger widths for hero resolution)
const HERO_IMAGES = [
  "/w7weugnjtvmxk7t4hbc6.jpg",
  "https://images.unsplash.com/photo-1547826039-bfc35e0f1ea8?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-160162161407e-12f0b9ca0448?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1505673542670-a5e3ff5b14a3?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1583212292454-1fe6229603b7?auto=format&fit=crop&w=1200&q=80",
  "https://images.unsplash.com/photo-1608976478546-d249d375369f?auto=format&fit=crop&w=1200&q=80"
];

export default function App() {
  const [places, setPlaces] = useState<Place[]>([]);
  const [selected, setSelected] = useState<Place | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playingAudio, setPlayingAudio] = useState<HTMLAudioElement | null>(null);
  const [isPlaceCollapsed, setIsPlaceCollapsed] = useState(false);
  const [currentHeroImgIdx, setCurrentHeroImgIdx] = useState(0);

  // Dynamic image transition for the Hero banner (every 3 seconds)
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentHeroImgIdx((prev) => (prev + 1) % HERO_IMAGES.length);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // ── 트랙 필터 상태 ─────────────────────────────────
  const [genreFilter, setGenreFilter] = useState<string | null>(null);
  const [commercialOnly, setCommercialOnly] = useState(false);
  // 장소 탐색 방식: 목록 / 권역별 소리 지도 (§8 Phase 6)
  const [placeView, setPlaceView] = useState<"list" | "map">("list");
  // 소리 지도에서 선택한 권역(설정 시 시놉시스 검색이 그 권역 안으로 한정됨)
  const [activeRegion, setActiveRegion] = useState<{ key: string; label: string } | null>(null);
  // 결과 패널(추천 국악 결과) — 선택 시 히어로까지 올라가지 않고 이 지점까지만 스크롤
  const resultsRef = useRef<HTMLDivElement>(null);
  const scrollToResults = () => {
    // 레이아웃이 갱신된 다음 프레임에 부드럽게 결과 패널 상단으로 이동
    requestAnimationFrame(() =>
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  };

  useEffect(() => {
    fetchPlaces()
      .then(setPlaces)
      .catch(() => setError("백엔드에 연결할 수 없습니다. 서버를 먼저 실행해 주세요."));
  }, []);

  // 장소 바뀌면 트랙 필터 초기화
  useEffect(() => {
    setGenreFilter(null);
    setCommercialOnly(false);
  }, [result]);

  // 필터·둘러보기 대상 목록: 권역 결과면 '이 권역의 국악 전체', 아니면 매칭 결과.
  const browseList = useMemo(
    () => (result ? result.region_tracks ?? result.tracks : []),
    [result],
  );

  // 목록에서 장르 추출 (중복 제거, 출현 순서 유지)
  const availableGenres = useMemo(() => {
    const seen = new Set<string>();
    const genres: string[] = [];
    for (const t of browseList) {
      if (!seen.has(t.genre)) { seen.add(t.genre); genres.push(t.genre); }
    }
    return genres;
  }, [browseList]);

  // 필터 적용
  const filteredTracks = useMemo(() => {
    return browseList.filter((t) => {
      if (genreFilter && t.genre !== genreFilter) return false;
      if (commercialOnly && t.commercial_ok !== true) return false;
      return true;
    });
  }, [browseList, genreFilter, commercialOnly]);

  const stopCurrentAudio = () => {
    if (playingAudio) {
      playingAudio.pause();
      playingAudio.currentTime = 0;
      setPlayingAudio(null);
    }
  };

  const handleSelect = async (place: Place) => {
    if (loading) return;
    setSelected(place);
    setIsPlaceCollapsed(true);
    setActiveRegion(null);     // 개별 장소 선택 → 권역 한정 해제
    setResult(null);
    setError(null);
    setLoading(true);
    stopCurrentAudio();
    scrollToResults();
    try {
      const data = await fetchMatch(place.id);
      setResult(data);
    } catch {
      setError("매칭 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegionSelect = async (regionKey: string) => {
    if (loading) return;
    setSelected(null);
    setIsPlaceCollapsed(false);
    // 이후 시놉시스 검색이 이 권역 안으로 한정되도록 활성 권역 기록
    setActiveRegion({ key: regionKey, label: REGION_META.find((r) => r.key === regionKey)?.label ?? regionKey });
    setResult(null);
    setError(null);
    setLoading(true);
    stopCurrentAudio();
    scrollToResults();
    try {
      const data = await fetchMatchByRegion(regionKey);
      setResult(data);
    } catch {
      setError("매칭 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (text: string) => {
    if (loading) return;
    setSelected(null);
    setIsPlaceCollapsed(false);
    setResult(null);
    setError(null);
    setLoading(true);
    stopCurrentAudio();
    scrollToResults();
    try {
      // 활성 권역이 있으면 그 권역 안에서 무드 검색, 없으면 전체 의미 검색
      const data = activeRegion
        ? await fetchMatchByRegionQuery(activeRegion.key, text)
        : await fetchMatchByText(text);
      setResult(data);
    } catch {
      setError("매칭 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const handlePlay = (audioEl: HTMLAudioElement) => {
    if (playingAudio && playingAudio !== audioEl) {
      playingAudio.pause();
      playingAudio.currentTime = 0;
    }
    if (playingAudio === audioEl && !audioEl.paused) {
      audioEl.pause();
      setPlayingAudio(null);
    } else {
      audioEl.onended = () => setPlayingAudio(null);
      audioEl.play().catch(() => {});
      setPlayingAudio(audioEl);
    }
  };

  // 탐색 방식(목록 ↔ 지도) 전환 시 현재 결과를 지워 빈 상태 안내로 되돌린다.
  const handleViewChange = (v: "list" | "map") => {
    if (v === placeView || loading) return;
    setPlaceView(v);
    setSelected(null);
    setIsPlaceCollapsed(false);
    setActiveRegion(null);
    setResult(null);
    setError(null);
    stopCurrentAudio();
  };

  const hasActiveFilter = genreFilter !== null || commercialOnly;

  return (
    <div className="min-h-screen bg-ivory">
      {/* 상단 내비게이션 — 반투명 아이보리, 가는 금박 하단선 */}
      <header className="sticky top-0 z-40 bg-ivory/80 backdrop-blur-md border-b border-gold/25">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center gap-4">
          <h1 className="text-xl font-serif font-semibold tracking-tight text-ink">
            <span className="text-gold">國樂</span>Place
          </h1>
          <div className="ml-auto hidden sm:flex items-center gap-6 text-xs text-stone-500">
            <span>하이브리드 매칭 엔진</span>
            <span className="text-stone-300">|</span>
            <span>지역 · 유형 · 의미 · 태그</span>
          </div>
        </div>
      </header>

      {/* 히어로 — 전통 사진 위 먹색 그라데이션, 명조 헤드라인 */}
      <section className="relative overflow-hidden bg-ink text-ivory h-[280px] sm:h-[350px]">
        {HERO_IMAGES.map((src, index) => (
          <img
            key={src}
            src={src}
            alt=""
            aria-hidden="true"
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-1000 ease-in-out brightness-105 ${
              index === currentHeroImgIdx ? "opacity-75" : "opacity-0"
            }`}
          />
        ))}
        <div className="absolute inset-0 bg-gradient-to-t from-ink/90 via-ink/45 to-ink/15" />
        <div className="relative max-w-[1600px] mx-auto px-6 py-20 sm:py-28">
          <p className="section-label text-gold-light mb-4">장소의 소리를 찾다</p>
          <h2 className="font-serif text-3xl sm:text-5xl font-semibold leading-tight tracking-tight max-w-2xl">
            장소의 문화 정체성과
            <br className="hidden sm:block" /> 국악을 잇다
          </h2>
          <div className="rule-gold w-24 my-6" />
          <p className="text-sm sm:text-base text-ivory/70 max-w-xl leading-relaxed">
            궁궐·한옥·시장의 결을 읽어, 그 장소에 어울리는 국악을 AI가 정성껏 골라 드립니다.
          </p>
        </div>
      </section>

      <main className="max-w-[1600px] mx-auto px-6 py-8">
        <div className="lg:grid lg:grid-cols-[600px_1fr] lg:gap-10">

        {/* ── 왼쪽: 탐색 패널 ── */}
        <div className="min-w-0">
          <div className="space-y-6 lg:sticky lg:top-8 lg:max-h-[calc(100vh-4rem)] lg:overflow-y-auto lg:pr-2">
            {/* selected가 있으면 장소 상세 정보 표시, 없으면 시놉시스 검색 표시 */}
            {selected ? (
              <div className="card overflow-hidden">
                {(() => {
                  const imageUrl = selected.image_url || FALLBACK_IMAGE[selected.type] || "https://images.unsplash.com/photo-1608976478546-d249d375369f?auto=format&fit=crop&w=600&q=80";
                  const imageCopyright = selected.image_url ? selected.image_copyright : "Type1";
                  return (
                    <div className="relative -mx-5 -mt-5 mb-4 h-48 overflow-hidden rounded-t-2xl">
                      <img
                        src={imageUrl}
                        alt={selected.name}
                        className="w-full h-full object-cover"
                      />
                      {imageCopyright && (
                        <span className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-full backdrop-blur-sm">
                          📸 이미지: {
                            imageCopyright === "Type1" ? "공공누리 제1유형" :
                            imageCopyright === "Type3" ? "공공누리 제3유형" :
                            imageCopyright === "Type2" ? "공공누리 제2유형" :
                            imageCopyright === "Type4" ? "공공누리 제4유형" :
                            imageCopyright
                          }
                        </span>
                      )}
                    </div>
                  );
                })()}
                <div className="flex items-start gap-4 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-xl font-bold">{selected.name}</h2>
                      <span className="badge">{selected.type}</span>
                      {selected.music_region !== "-" && (
                        <span className="badge">{selected.music_region} 권역</span>
                      )}
                    </div>
                    <p className="text-sm text-stone-600 mt-2 leading-relaxed">
                      {selected.description}
                    </p>
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {selected.cultural_keywords.map((kw) => (
                        <span key={kw} className="badge bg-jade/10 text-jade">
                          #{kw}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <SelectedPlaceMap place={selected} />
              </div>
            ) : (
              <SynopsisSearch
                onSearch={handleSearch}
                loading={loading}
                scopeLabel={activeRegion?.label ?? null}
                onClearScope={() => setActiveRegion(null)}
              />
            )}

            {/* 구분선 */}
            <div className="flex items-center gap-3 text-xs text-stone-400">
              <div className="flex-1 rule-gold" />
              또는 장소로 찾기
              <div className="flex-1 rule-gold" />
            </div>

            {/* 목록 / 소리 지도 토글 */}
            <div className="flex justify-center gap-1.5">
              {([["list", "목록"], ["map", "전국 소리 지도"]] as const).map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => handleViewChange(v)}
                  className={`px-4 py-1.5 text-xs rounded-full border transition-colors ${
                    placeView === v
                      ? "bg-jade text-white border-jade"
                      : "border-stone-200 text-stone-500 hover:border-jade hover:text-jade"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* 장소 선택: 목록 또는 지도(마커 클릭 → 매칭) */}
            {placeView === "list" ? (
              <PlaceSelector
                places={places}
                selected={selected}
                onSelect={handleSelect}
                loading={loading}
                collapsed={isPlaceCollapsed}
                onExpand={() => {
                  setIsPlaceCollapsed(false);
                  setSelected(null);
                  setResult(null);
                  stopCurrentAudio();
                }}
              />
            ) : (
              <RegionSoundMap
                places={places}
                selected={selected}
                onSelect={handleSelect}
                onRegionSelect={handleRegionSelect}
                loading={loading}
              />
            )}
          </div>
        </div>

        {/* ── 오른쪽: 결과 패널 ── */}
        <div ref={resultsRef} className="mt-8 lg:mt-0 min-w-0 scroll-mt-20">

        {/* 빈 상태 안내 (데스크톱에서 오른쪽 여백 방지) */}
        {!loading && !error && !result && (
          <div className="hidden lg:block lg:sticky lg:top-8">
            <h2 className="section-label mb-3 block">
              추천 국악 결과
            </h2>
            <div className="card text-center text-stone-400 py-12 min-h-[190px] flex flex-col justify-center items-center">
              <div className="font-serif text-4xl text-gold/40 mb-3 select-none">樂</div>
              <p className="text-sm leading-relaxed text-stone-500">
                왼쪽에서 장소·권역을 클릭하거나 장면을 입력하면<br />
                추천 국악이 여기에 나타납니다.
              </p>
            </div>
          </div>
        )}

        {/* 로딩 */}
        {loading && (
          <div className="flex items-center justify-center py-16 gap-3 text-stone-500">
            <div className="w-5 h-5 border-2 border-jade border-t-transparent rounded-full animate-spin" />
            <span>AI 매칭 중…</span>
          </div>
        )}

        {/* 오류 */}
        {error && (
          <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 px-5 py-4 text-sm">
            {error}
          </div>
        )}

        {/* 결과 */}
        {result && !loading && (
          <section className="animate-fade-in">
            <h2 className="section-label mb-3 block">
              추천 국악 결과
            </h2>
            {/* 장소 정보 (자유 텍스트 검색 결과로 매칭된 장소인 경우에만 우측에 표시) */}
            {!selected && (
              <div className="card mb-6 overflow-hidden">
                {(() => {
                  const imageUrl = result.place.image_url || FALLBACK_IMAGE[result.place.type] || "https://images.unsplash.com/photo-1608976478546-d249d375369f?auto=format&fit=crop&w=600&q=80";
                  const imageCopyright = result.place.image_url ? result.place.image_copyright : "Type1";
                  return (
                    <div className="relative -mx-5 -mt-5 mb-4 h-48 overflow-hidden rounded-t-2xl">
                      <img
                        src={imageUrl}
                        alt={result.place.name}
                        className="w-full h-full object-cover"
                      />
                      {imageCopyright && (
                        <span className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-full backdrop-blur-sm">
                          📸 이미지: {
                            imageCopyright === "Type1" ? "공공누리 제1유형" :
                            imageCopyright === "Type3" ? "공공누리 제3유형" :
                            imageCopyright === "Type2" ? "공공누리 제2유형" :
                            imageCopyright === "Type4" ? "공공누리 제4유형" :
                            imageCopyright
                          }
                        </span>
                      )}
                    </div>
                  );
                })()}
                <div className="flex items-start gap-4 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-xl font-bold">{result.place.name}</h2>
                      <span className="badge">{result.place.type}</span>
                      {result.place.music_region !== "-" && (
                        <span className="badge">{result.place.music_region} 권역</span>
                      )}
                    </div>
                    <p className="text-sm text-stone-600 mt-2 leading-relaxed">
                      {result.place.description}
                    </p>
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {result.place.cultural_keywords.map((kw) => (
                        <span key={kw} className="badge bg-jade/10 text-jade">
                          #{kw}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                {/* 권역 매칭 결과에서는 위치 지도를 숨긴다 — 전국 소리 지도가 이미 권역을 보여줌 */}
                {!result.region_tracks && <SelectedPlaceMap place={result.place} />}
              </div>
            )}

            {/* 권역 모드: 추천(top)을 먼저 강조하고, 아래에 권역 전체 목록을 둘러보게 한다 */}
            {result.region_tracks && result.tracks.length > 0 && (
              <div className="mb-8">
                <h2 className="section-label mb-3 block">
                  이 권역 추천 {result.tracks.length}곡
                </h2>
                <div className="space-y-4">
                  {result.tracks.map((track, i) => (
                    <TrackCard
                      key={`rec-${track.id}`}
                      track={track}
                      rank={i + 1}
                      isPlaying={playingAudio?.src.endsWith(track.audio_path) ?? false}
                      onPlay={handlePlay}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* 매칭 헤더 + 필터 (권역: 전체 목록 / 그 외: 매칭 결과) */}
            <div className="mb-4 space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="section-label">
                  {result.region_tracks ? "이 권역의 국악 전체" : "AI 매칭 결과"}
                </h2>
                <span className="text-xs text-stone-400">
                  {filteredTracks.length} / {browseList.length}곡
                </span>
              </div>

              {/* 장르 필터 칩 */}
              {availableGenres.length > 1 && (
                <div className="flex flex-wrap gap-1.5">
                  <button
                    onClick={() => setGenreFilter(null)}
                    className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                      !genreFilter
                        ? "bg-jade text-white border-jade"
                        : "border-stone-200 text-stone-500 hover:border-jade hover:text-jade"
                    }`}
                  >
                    전체 장르
                  </button>
                  {availableGenres.map((g) => (
                    <button
                      key={g}
                      onClick={() => setGenreFilter(genreFilter === g ? null : g)}
                      className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                        genreFilter === g
                          ? "bg-jade text-white border-jade"
                          : "border-stone-200 text-stone-500 hover:border-jade hover:text-jade"
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              )}

              {/* 라이선스 필터 */}
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2 text-xs text-stone-500 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={commercialOnly}
                    onChange={(e) => setCommercialOnly(e.target.checked)}
                    className="accent-jade w-3.5 h-3.5"
                  />
                  수익화 가능 음원만 보기
                </label>
                {hasActiveFilter && (
                  <button
                    className="text-xs text-stone-400 underline underline-offset-2 hover:text-stone-600"
                    onClick={() => { setGenreFilter(null); setCommercialOnly(false); }}
                  >
                    필터 초기화
                  </button>
                )}
              </div>
            </div>

            {/* 트랙 카드 목록 */}
            {filteredTracks.length > 0 ? (
              <div className="space-y-4">
                {filteredTracks.map((track, i) => (
                  <TrackCard
                    key={track.id}
                    track={track}
                    rank={i + 1}
                    isPlaying={playingAudio?.src.endsWith(track.audio_path) ?? false}
                    onPlay={handlePlay}
                    hideScore={!!result.region_tracks}
                  />
                ))}
              </div>
            ) : (
              <div className="py-10 text-center text-sm text-stone-400 rounded-xl border border-dashed border-stone-300/70">
                <div className="font-serif text-3xl text-gold/40 mb-2 select-none">音</div>
                <p>현재 필터 조건에 맞는 곡이 없습니다.</p>
                <button
                  className="mt-2 text-xs text-jade underline underline-offset-2"
                  onClick={() => { setGenreFilter(null); setCommercialOnly(false); }}
                >
                  필터 초기화
                </button>
              </div>
            )}

            {/* BGM 생성 — 실제 장소만(합성 권역·자유검색 place는 생성 대상 아님) */}
            {!result.place.id.startsWith("__") && (
              <div className="mt-6">
                <GenerateBGM placeId={result.place.id} />
              </div>
            )}

            {/* 안내 */}
            <p className="mt-4 text-xs text-stone-400 text-center">
              모든 음원은 이용 조건이 명확한 공공 국악·자유이용 음원입니다.
              음원별 출처·라이선스를 반드시 확인하세요.
            </p>
          </section>
        )}
        </div>{/* /오른쪽 결과 패널 */}
        </div>{/* /2단 그리드 */}
      </main>
    </div>
  );
}
