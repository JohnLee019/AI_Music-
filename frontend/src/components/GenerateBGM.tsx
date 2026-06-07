import { useRef, useState } from "react";
import { fetchGenerate } from "../api";
import type { BgmLicense } from "../api";

interface Props {
  placeId: string;
}

export default function GenerateBGM({ placeId }: Props) {
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [generated, setGenerated] = useState(true);
  const [fallbackTitle, setFallbackTitle] = useState<string>("");
  const [license, setLicense] = useState<BgmLicense | null>(null);
  const [copied, setCopied] = useState(false);
  const [prompt, setPrompt] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);

  const MAX_PROMPT = 200;

  const handleGenerate = async () => {
    const el = audioRef.current;
    // autoplay 잠금 해제: 클릭 즉시(동기적으로) 권한 확보 → fetch 후 src 교체해 play()
    // (audio 엘리먼트를 항상 마운트해 두어야 클릭 시점에 ref가 살아있다)
    if (el) el.play().then(() => el.pause()).catch(() => {});

    setStatus("loading");
    try {
      const { audio_url, generated: gen, fallback_title, license: lic } = await fetchGenerate(placeId, prompt);
      if (!audio_url) { setStatus("error"); return; }
      setAudioUrl(audio_url);
      setGenerated(gen !== false);
      setFallbackTitle(fallback_title ?? "");
      setLicense(lic ?? null);
      setStatus("done");
      if (el) {
        el.src = audio_url;
        el.play().catch(() => {});
      }
    } catch {
      setStatus("error");
    }
  };

  const handleCopyLicense = async () => {
    if (!license?.attribution_text) return;
    try {
      await navigator.clipboard.writeText(license.attribution_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 클립보드 권한 실패 시 무시 (문구는 화면에 노출돼 있음)
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

      {/* 사용자 프롬프트(선택) — 장소·매칭곡 정보와 합쳐져 생성에 반영된다 */}
      <div className="mt-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value.slice(0, MAX_PROMPT))}
          disabled={status === "loading"}
          rows={2}
          placeholder="원하는 분위기를 적어보세요 (선택) — 예: 비 오는 밤, 느리고 쓸쓸하게"
          className="w-full text-xs rounded-lg border border-stone-200 bg-white px-2.5 py-1.5
                     placeholder:text-stone-400 focus:border-jade focus:outline-none resize-none"
        />
        <div className="flex justify-between text-[10px] text-stone-400 mt-0.5">
          <span>장소 정보(키워드·악기·분위기)에 입력 내용이 더해집니다.</span>
          <span>{prompt.length}/{MAX_PROMPT}</span>
        </div>
      </div>
      {/* audio 엘리먼트는 항상 마운트 — 클릭 시점에 ref가 살아있어야 autoplay unlock이 동작한다 */}
      <div className={status === "done" && audioUrl ? "mt-3" : "hidden"}>
        <audio ref={audioRef} controls className="w-full h-8" />
        <p className="text-xs text-stone-400 mt-1">
          {generated
            ? "AI 생성 BGM (ElevenLabs Music)"
            : `생성 실패 — 가장 잘 맞는 기존 음원${fallbackTitle ? ` «${fallbackTitle}»` : ""}을 제공합니다`}
        </p>

        {/* 라이선스 / 출처표시 — 복사해 영상 크레딧에 붙여 넣을 수 있다 */}
        {license && (
          <div className="mt-2 rounded-lg bg-stone-50 border border-stone-200 p-2.5">
            <div className="flex flex-wrap gap-1.5 text-[11px] mb-1.5">
              <span className="badge-license bg-green-100 text-green-700">{license.license_type}</span>
              {license.commercial_ok ? (
                <span className="badge-license bg-emerald-50 text-emerald-700">수익화 가능</span>
              ) : license.personal_use_only ? (
                <span className="badge-license bg-amber-50 text-amber-700">개인적 사용</span>
              ) : null}
              {license.derivative_ok && (
                <span className="badge-license bg-sky-50 text-sky-700">편집 가능</span>
              )}
            </div>
            <p className="text-[11px] text-stone-700 leading-relaxed break-keep">
              {license.attribution_text}
            </p>
            {license.source_url && (
              <p className="text-[11px] text-stone-400 mt-0.5 break-all">{license.source_url}</p>
            )}
            <button
              onClick={handleCopyLicense}
              className="mt-1.5 w-full text-[11px] py-1 rounded-lg border border-stone-200
                         text-stone-600 hover:border-jade hover:text-jade transition-colors"
            >
              {copied ? "✓ 복사됨" : "📋 출처 문구 복사"}
            </button>
            <p className="mt-1.5 text-[10px] text-stone-400 leading-relaxed">
              {license.personal_use_only
                ? "※ AI 생성물은 ElevenLabs 약관을 따릅니다. 위 문구로 출처를 표시하고 개인적 용도로 사용하세요. 상업적 이용은 별도 권리 확인이 필요합니다."
                : "※ 출처표시는 법적 의무입니다. 위 문구를 영상 더보기란(크레딧)에 그대로 붙여 넣어 주세요."}
            </p>
          </div>
        )}
      </div>
      {status === "error" && (
        <p className="mt-2 text-xs text-red-500">생성 실패. 인터넷 연결이나 API 키를 확인하세요.</p>
      )}
    </div>
  );
}
