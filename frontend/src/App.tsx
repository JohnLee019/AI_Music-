import { useEffect, useRef, useState } from "react";
import type { MatchResult, Place } from "./api";
import { fetchMatch, fetchPlaces } from "./api";
import GenerateBGM from "./components/GenerateBGM";
import PlaceSelector from "./components/PlaceSelector";
import TrackCard from "./components/TrackCard";

export default function App() {
  const [places, setPlaces] = useState<Place[]>([]);
  const [selected, setSelected] = useState<Place | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playingAudio, setPlayingAudio] = useState<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetchPlaces()
      .then(setPlaces)
      .catch(() => setError("백엔드에 연결할 수 없습니다. 서버를 먼저 실행해 주세요."));
  }, []);

  const handleSelect = async (place: Place) => {
    if (loading) return;
    setSelected(place);
    setResult(null);
    setError(null);
    setLoading(true);
    // 현재 재생 중인 오디오 정지
    stopCurrentAudio();
    try {
      const data = await fetchMatch(place.id);
      setResult(data);
    } catch {
      setError("매칭 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const stopCurrentAudio = () => {
    if (playingAudio) {
      playingAudio.pause();
      playingAudio.currentTime = 0;
      setPlayingAudio(null);
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
      audioEl.play().catch(() => {});
      setPlayingAudio(audioEl);
    }
  };

  return (
    <div className="min-h-screen bg-hanji">
      {/* 헤더 */}
      <header className="bg-ink text-hanji py-5 px-6 shadow-lg">
        <div className="max-w-4xl mx-auto flex items-end gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gold">國樂</span>Place
            </h1>
            <p className="text-xs text-stone-400 mt-0.5">
              장소의 문화 정체성과 국악을 AI로 매칭합니다
            </p>
          </div>
          <div className="ml-auto text-right hidden sm:block">
            <div className="text-xs text-stone-500">하이브리드 매칭 엔진</div>
            <div className="text-xs text-stone-600">지역 · 유형 · 의미 · 태그</div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* 장소 선택 */}
        <PlaceSelector
          places={places}
          selected={selected}
          onSelect={handleSelect}
          loading={loading}
        />

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
          <section>
            {/* 장소 정보 */}
            <div className="card mb-6">
              <div className="flex items-start gap-4 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-xl font-bold">{result.place.name}</h2>
                    <span className="badge">{result.place.type}</span>
                    <span className="badge">{result.place.music_region} 권역</span>
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
            </div>

            {/* 매칭 헤더 */}
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-medium text-stone-500 tracking-widest uppercase">
                AI 매칭 결과
              </h2>
              <span className="text-xs text-stone-400">
                {result.tracks.length}곡 중 상위 선곡
              </span>
            </div>

            {/* 트랙 카드 목록 */}
            <div className="space-y-4">
              {result.tracks.map((track, i) => (
                <TrackCard
                  key={track.id}
                  track={track}
                  rank={i + 1}
                  isPlaying={playingAudio?.src.endsWith(track.audio_path) ?? false}
                  onPlay={handlePlay}
                />
              ))}
            </div>

            {/* BGM 생성 */}
            <div className="mt-6">
              <GenerateBGM placeId={result.place.id} />
            </div>

            {/* 안내 */}
            <p className="mt-4 text-xs text-stone-400 text-center">
              모든 음원은 이용 조건이 명확한 공공 국악·자유이용 음원입니다.
              음원별 출처·라이선스를 반드시 확인하세요.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}
