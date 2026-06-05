import { useState } from "react";
import type { Track } from "../api";

interface Props {
  track: Track;
  onClose: () => void;
}

/** 파일명에 쓸 수 없는 문자를 정리. */
function safeFileName(title: string, ext: string): string {
  const base = title.replace(/[\\/:*?"<>|]+/g, "_").trim().slice(0, 60);
  return `${base}${ext}`;
}

export default function AttributionModal({ track, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  const attribution =
    track.attribution_text ??
    `«${track.title}» / ${track.source} / ${track.license_type}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(attribution);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 클립보드 권한 실패 시 무시 (텍스트는 화면에 노출돼 있음)
    }
  };

  const handleDownload = () => {
    const ext = track.audio_path.slice(track.audio_path.lastIndexOf("."));
    const a = document.createElement("a");
    a.href = track.audio_path; // /audio/* 는 백엔드로 프록시됨
    a.download = safeFileName(track.title, ext || ".mp3");
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="card max-w-md w-full bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-base">출처표시 후 다운로드</h3>
            <p className="text-xs text-stone-500 mt-0.5">«{track.title}»</p>
          </div>
          <button
            aria-label="닫기"
            onClick={onClose}
            className="text-stone-400 hover:text-stone-600 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* 라이선스 요약 */}
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          <span className="badge-license bg-green-100 text-green-700">{track.license_type}</span>
          {track.commercial_ok && (
            <span className="badge-license bg-emerald-50 text-emerald-700">수익화 가능</span>
          )}
          {track.derivative_ok && (
            <span className="badge-license bg-sky-50 text-sky-700">편집 가능</span>
          )}
        </div>

        {/* 안내 */}
        <p className="mt-3 text-xs text-stone-600 leading-relaxed">
          이 음원은 <b>이용 조건(출처표시)을 지키면</b> 영상에 사용·수익화·편집할 수 있습니다.
          아래 문구를 <b>영상 더보기란(크레딧)에 그대로</b> 붙여 넣어 주세요. 출처표시는 법적 의무입니다.
        </p>

        {/* 출처표시 문구 */}
        <div className="mt-2 rounded-lg bg-stone-50 border border-stone-200 p-3">
          <p className="text-xs text-stone-700 leading-relaxed break-keep">{attribution}</p>
          {track.source_url && (
            <p className="text-xs text-stone-400 mt-1 break-all">{track.source_url}</p>
          )}
        </div>

        <button
          onClick={handleCopy}
          className="mt-2 w-full text-xs py-1.5 rounded-lg border border-stone-200
                     text-stone-600 hover:border-jade hover:text-jade transition-colors"
        >
          {copied ? "✓ 복사됨" : "📋 출처 문구 복사"}
        </button>

        {/* 다운로드 */}
        <button
          onClick={handleDownload}
          className="btn-primary w-full mt-3 py-2 text-sm"
        >
          ⬇ 음원 다운로드
        </button>

        <p className="mt-2 text-[11px] text-stone-400 leading-relaxed">
          ※ 본 서비스는 이용 조건 확인을 돕는 도구이며, 법적 면책을 보증하는 인증서를 발급하지 않습니다.
          최종 이용 책임은 사용자에게 있습니다.
        </p>
      </div>
    </div>
  );
}
