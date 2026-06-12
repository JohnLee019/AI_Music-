import { useRef, useState } from "react";
import type { Track } from "../api";
import AttributionModal from "./AttributionModal";
import ScoreBar from "./ScoreBar";
import ScoreRadar from "./ScoreRadar";

interface Props {
  track: Track;
  rank: number;
  isPlaying: boolean;
  onPlay: (audioEl: HTMLAudioElement) => void;
  hideScore?: boolean;
}

const LICENSE_STYLE: Record<string, string> = {
  "CC BY": "bg-green-100 text-green-700",
  "CC BY-SA": "bg-blue-100 text-blue-700",
  "CC BY-ND": "bg-yellow-100 text-yellow-700",
  "CC BY-NC": "bg-orange-100 text-orange-700",
};

// 헤드라인 점수 표시 보정 (표시 전용 — 순위·score_detail·레이더는 원값 유지).
// 원점수(가중합)는 태그 축이 실데이터에서 거의 0이고(전 쌍의 99.3%) 의미 유사도도
// 좁은 띠(0.57~0.84)에 몰려, 실질 범위가 [0.35, 0.85]로 눌려 만점이 불가능하다.
// 이 실질 범위를 [50, 99]로 펴서 "추천인데 37점"처럼 읽히는 왜곡을 막는다.
const RAW_SCORE_FLOOR = 0.35; // 추천권 실질 하한 (전국 BGM: 지역 0.6×30% + 유형 0.5×25%)
const RAW_SCORE_CEIL = 0.85;  // 실질 상한 (태그 축 미발화 시 도달 가능한 최대치)
const DISPLAY_MIN = 50;
const DISPLAY_MAX = 99;

function displayScore(score: number): number {
  const s = Math.min(RAW_SCORE_CEIL, Math.max(RAW_SCORE_FLOOR, score));
  const ratio = (s - RAW_SCORE_FLOOR) / (RAW_SCORE_CEIL - RAW_SCORE_FLOOR);
  return Math.round(DISPLAY_MIN + ratio * (DISPLAY_MAX - DISPLAY_MIN));
}

function fmtTime(t: number): string {
  if (!isFinite(t) || t < 0) return "0:00";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function TrackCard({ track, rank, isPlaying, onPlay, hideScore = false }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const [showScores, setShowScores] = useState(false);
  const [showDownload, setShowDownload] = useState(false);
  const [time, setTime] = useState(0);
  const [dur, setDur] = useState(0);

  const playable = track.audio_available !== false;
  // 크리에이터 다운로드 허용 = 수익화 + 편집 모두 가능 (AGENTS.md §5.5 creator)
  const creatorSafe = track.commercial_ok === true && track.derivative_ok === true;
  const licenseStyle = LICENSE_STYLE[track.license_type] ?? "bg-stone-100 text-stone-600";

  const handlePlayClick = () => {
    const el = audioRef.current;
    if (el) onPlay(el);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    const el = audioRef.current;
    if (el) {
      el.currentTime = v;
      setTime(v);
    }
  };

  return (
    <div
      className={`card transition-all ${
        isPlaying ? "ring-2 ring-persimmon border-persimmon" : ""
      }`}
    >
      {/* 헤더 */}
      <div className="flex items-start gap-3">
        <span className="font-serif text-3xl text-stone-300 leading-none select-none">
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
            {track.asset_kind === "sample_loop" && (
              <span className="badge bg-violet-50 text-violet-600">편집 루프</span>
            )}
            <span className={`badge-license ${licenseStyle}`}>{track.license_type}</span>
            {/* 3-state 라이선스 배지 (AGENTS.md §8) */}
            {track.commercial_ok === true ? (
              <span className="badge-license bg-emerald-50 text-emerald-700">수익화 OK</span>
            ) : (
              <span className="badge-license bg-red-50 text-red-500">수익화 불가</span>
            )}
            {track.derivative_ok === true ? (
              <span className="badge-license bg-sky-50 text-sky-700">편집 OK</span>
            ) : (
              <span className="badge-license bg-orange-50 text-orange-500">편집 불가</span>
            )}
            <span className="badge-license bg-stone-100 text-stone-500">출처표시 필수</span>
          </div>
        </div>
        {/* 매칭 점수 */}
        {!hideScore && (
          <div className="shrink-0 text-right">
            <div className="text-lg font-bold text-jade">{displayScore(track.score)}</div>
            <div className="text-xs text-stone-400">점</div>
          </div>
        )}
      </div>

      {/* 악기 / 분위기 */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {track.instruments.slice(0, 5).map((ins) => (
          <span key={ins} className="badge">{ins}</span>
        ))}
        {track.mood.slice(0, 3).map((m) => (
          <span key={m} className="badge bg-gold/10 text-gold">{m}</span>
        ))}
      </div>

      {/* 점수 세부: 레이더 차트(AI 가시화) + 보조 ScoreBar (AGENTS.md §8) */}
      {!hideScore && (
        <div className="mt-3">
          <button
            className="text-xs text-jade underline underline-offset-2 hover:text-jade/70"
            onClick={() => setShowScores((v) => !v)}
          >
            {showScores ? "점수 차트 숨기기" : "매칭 점수 보기"}
          </button>
          {showScores && (
            <>
              <ScoreRadar scores={track.score_detail} />
              <div className="mt-2 space-y-1 sm:hidden">
                <ScoreBar label="지역" value={track.score_detail.region} color="bg-sky-400" />
                <ScoreBar label="유형" value={track.score_detail.type} color="bg-violet-400" />
                <ScoreBar label="의미" value={track.score_detail.semantic} color="bg-jade" />
                <ScoreBar label="태그" value={track.score_detail.tag} color="bg-gold" />
              </div>
            </>
          )}
        </div>
      )}

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

      {/* 시크바 (재생 위치 조절) — 재생 가능한 곡만 */}
      {playable && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-stone-400 tabular-nums w-9 text-right">{fmtTime(time)}</span>
          <input
            type="range"
            min={0}
            max={dur || 0}
            step={0.1}
            value={time}
            onChange={handleSeek}
            className="flex-1 h-1.5 accent-persimmon cursor-pointer"
            aria-label="재생 위치"
          />
          <span className="text-xs text-stone-400 tabular-nums w-9">{fmtTime(dur)}</span>
        </div>
      )}

      {/* 오디오 플레이어 */}
      <div className="mt-3 flex items-center gap-3">
        <audio
          ref={audioRef}
          src={track.audio_path}
          preload="metadata"
          onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        />
        {playable ? (
          <button
            className={`btn-primary text-xs px-4 py-1.5 inline-flex items-center gap-1.5 ${
              isPlaying ? "bg-persimmon hover:bg-persimmon/90" : ""
            }`}
            onClick={handlePlayClick}
          >
            {isPlaying ? (
              <>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
                일시정지
              </>
            ) : (
              <>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5.5v13a1 1 0 0 0 1.5.87l11-6.5a1 1 0 0 0 0-1.74l-11-6.5A1 1 0 0 0 7 5.5Z" /></svg>
                재생
              </>
            )}
          </button>
        ) : (
          <span
            className="text-xs px-4 py-1.5 rounded-lg border border-stone-200 text-stone-300 cursor-not-allowed select-none"
            title="이 곡은 카탈로그에 있으나 미리듣기 음원이 아직 준비되지 않았습니다"
          >
            미리듣기 준비중
          </span>
        )}

        {/* 크리에이터 다운로드: 수익화+편집 가능 음원만 */}
        {creatorSafe ? (
          <button
            className="text-xs px-3 py-1.5 rounded-lg border border-jade text-jade inline-flex items-center gap-1.5
                       hover:bg-jade hover:text-white transition-colors"
            onClick={() => setShowDownload(true)}
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" /></svg>
            다운로드
          </button>
        ) : (
          <span
            className="text-xs px-3 py-1.5 rounded-lg border border-stone-200 text-stone-300 cursor-not-allowed"
            title="수익화 또는 편집 조건을 충족하지 않아 크리에이터 다운로드를 제공하지 않습니다"
          >
            다운로드
          </span>
        )}

        <span className="text-xs text-stone-400 ml-auto">{track.region} 권역</span>
      </div>

      {showDownload && (
        <AttributionModal track={track} onClose={() => setShowDownload(false)} />
      )}
    </div>
  );
}
