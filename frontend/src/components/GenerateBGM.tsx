import { useRef, useState } from "react";
import { fetchGenerate } from "../api";

interface Props {
  placeId: string;
}

export default function GenerateBGM({ placeId }: Props) {
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const handleGenerate = async () => {
    const el = audioRef.current;
    // autoplay 잠금 해제
    if (el) el.play().then(() => el.pause()).catch(() => {});

    setStatus("loading");
    try {
      const { audio_url } = await fetchGenerate(placeId);
      setAudioUrl(audio_url);
      setStatus("done");
      if (el) {
        el.src = audio_url;
        el.play().catch(() => {});
      }
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="card border-dashed border-stone-300 bg-stone-50/50">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="font-semibold text-sm">✨ 맞춤 BGM 생성</div>
          <div className="text-xs text-stone-500 mt-0.5">
            AI가 이 장소에 어울리는 국악 색 BGM을 생성합니다.
          </div>
        </div>
        <button
          className="btn-secondary text-xs"
          disabled={status === "loading"}
          onClick={handleGenerate}
        >
          {status === "loading" ? "생성 중…" : "생성하기"}
        </button>
      </div>
      {status === "done" && audioUrl && (
        <div className="mt-3">
          <audio ref={audioRef} controls className="w-full h-8" />
          <p className="text-xs text-stone-400 mt-1">생성된 BGM (라이선스 클린 모델 사용)</p>
        </div>
      )}
      {status === "error" && (
        <p className="mt-2 text-xs text-red-500">생성 실패. 인터넷 연결이나 API 키를 확인하세요.</p>
      )}
    </div>
  );
}
