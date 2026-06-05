import { useRef, useState } from "react";
import type { Track } from "../api";
import ScoreBar from "./ScoreBar";

interface Props {
  track: Track;
  rank: number;
  isPlaying: boolean;
  onPlay: (audioEl: HTMLAudioElement) => void;
}

const LICENSE_STYLE: Record<string, string> = {
  "CC BY": "bg-green-100 text-green-700",
  "CC BY-SA": "bg-blue-100 text-blue-700",
  "CC BY-ND": "bg-yellow-100 text-yellow-700",
  "CC BY-NC": "bg-orange-100 text-orange-700",
};

export default function TrackCard({ track, rank, isPlaying, onPlay }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [showReasoning, setShowReasoning] = useState(false);

  const handlePlayClick = () => {
    const el = audioRef.current;
    if (!el) return;
    // 재생 버튼 클릭은 그 자체가 사용자 제스처 → 별도 unlock 없이 바로 토글.
    // (play→pause 후 즉시 play()를 또 부르면 deferred pause가 재생을 죽이는 경쟁 상태 발생)
    onPlay(el);
  };

  const licenseStyle = LICENSE_STYLE[track.license_type] ?? "bg-stone-100 text-stone-600";

  return (
    <div
      className={`card transition-all ${
        isPlaying ? "ring-2 ring-persimmon border-persimmon" : ""
      }`}
    >
      {/* 헤더 */}
      <div className="flex items-start gap-3">
        <span className="text-2xl font-bold text-stone-200 leading-none select-none">
          {String(rank).padStart(2, "0")}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-base truncate">{track.title}</h3>
            {isPlaying && (
              <span className="flex items-center gap-1 text-xs text-persimmon font-medium">
                <span className="animate-pulse">●</span> 재생 중
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span className="badge">{track.genre}</span>
            {track.sub_genre && track.sub_genre !== track.genre && (
              <span className="badge">{track.sub_genre}</span>
            )}
            <span className={`badge-license ${licenseStyle}`}>{track.license_type}</span>
            {track.commercial_ok === true && (
              <span className="badge-license bg-emerald-50 text-emerald-700">수익화 가능</span>
            )}
            {track.commercial_ok === false && (
              <span className="badge-license bg-red-50 text-red-500">비상업</span>
            )}
            {track.derivative_ok === true && (
              <span className="badge-license bg-sky-50 text-sky-700">편곡 허용</span>
            )}
          </div>
        </div>
        {/* 매칭 점수 */}
        <div className="shrink-0 text-right">
          <div className="text-lg font-bold text-jade">
            {Math.round(track.score * 100)}
          </div>
          <div className="text-xs text-stone-400">점</div>
        </div>
      </div>

      {/* 악기 / 분위기 */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {track.instruments.slice(0, 5).map((ins) => (
          <span key={ins} className="badge">🎵 {ins}</span>
        ))}
        {track.mood.slice(0, 3).map((m) => (
          <span key={m} className="badge bg-orange-50 text-orange-600">✦ {m}</span>
        ))}
      </div>

      {/* 점수 세부 */}
      <div className="mt-3 space-y-1">
        <ScoreBar label="지역" value={track.score_detail.region} color="bg-sky-400" />
        <ScoreBar label="유형" value={track.score_detail.type} color="bg-violet-400" />
        <ScoreBar label="의미" value={track.score_detail.semantic} color="bg-jade" />
        <ScoreBar label="태그" value={track.score_detail.tag} color="bg-gold" />
      </div>

      {/* AI 매칭 근거 */}
      <div className="mt-3">
        <button
          className="text-xs text-jade underline underline-offset-2 hover:text-jade/70"
          onClick={() => setShowReasoning((v) => !v)}
        >
          {showReasoning ? "근거 숨기기" : "AI 매칭 근거 보기"}
        </button>
        {showReasoning && (
          <p className="mt-1.5 text-xs text-stone-600 leading-relaxed bg-stone-50 rounded-lg p-3">
            {track.reasoning}
          </p>
        )}
      </div>

      {/* 출처 */}
      <div className="mt-2 text-xs text-stone-400">
        출처: {track.source} · {track.license_note}
      </div>

      {/* 오디오 플레이어 */}
      <div className="mt-3 flex items-center gap-3">
        <audio ref={audioRef} src={track.audio_path} preload="none" />
        <button
          className={`btn-primary text-xs px-4 py-1.5 ${
            isPlaying
              ? "bg-persimmon hover:bg-persimmon/80"
              : ""
          }`}
          onClick={handlePlayClick}
        >
          {isPlaying ? "⏸ 일시정지" : "▶ 재생"}
        </button>
        <span className="text-xs text-stone-400">
          {track.region} 권역
        </span>
      </div>
    </div>
  );
}
