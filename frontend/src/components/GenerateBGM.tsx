import { useEffect, useRef, useState } from "react";
import { fetchGenerate, fetchPoems } from "../api";
import type { BgmLicense, GenerateTarget, Poem } from "../api";

interface Props {
  placeId?: string;
  region?: string;       // 소리 지도 권역 key — 권역 정보(+사용자 프롬프트 길이 가중)로 생성
  regionLabel?: string;  // 권역 표기명 (안내 문구용)
}

// 진행 단계: 분위기 입력 → (보내기) → 시 추천·선택.
type Step = "input" | "choose";

export default function GenerateBGM({ placeId, region, regionLabel }: Props) {
  // API 호출 대상 — 실제 장소 또는 소리 지도 권역.
  const target: GenerateTarget = placeId ? { placeId } : { region };
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [generated, setGenerated] = useState(true);
  const [fallbackTitle, setFallbackTitle] = useState<string>("");
  const [license, setLicense] = useState<BgmLicense | null>(null);
  const [usedPoem, setUsedPoem] = useState<Poem | null>(null);  // 생성에 실제 쓰인 시(결과 표시용)
  const [copied, setCopied] = useState(false);
  const [prompt, setPrompt] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);

  // ── 고전 시 추천·선택 상태 ────────────────────────────
  const [step, setStep] = useState<Step>("input");
  const [poems, setPoems] = useState<Poem[]>([]);
  const [recommendedId, setRecommendedId] = useState<string | null>(null);
  const [poemsLoading, setPoemsLoading] = useState(false);
  const [rankedBy, setRankedBy] = useState<string | null>(null);  // 추천에 쓰인 무드 프롬프트
  const [selectedId, setSelectedId] = useState<string | null>(null);  // 고른 시 id
  const [expandedId, setExpandedId] = useState<string | null>(null);  // 본문을 펼친 시 id

  const MAX_PROMPT = 200;
  const busy = status === "loading";

  // 장소(또는 권역)가 바뀌면 입력 단계로 초기화(추천은 사용자가 '보내기'를 눌렀을 때 계산).
  useEffect(() => {
    setStatus("idle");
    setAudioUrl(null);
    setUsedPoem(null);
    setPrompt("");
    setStep("input");
    setPoems([]);
    setRecommendedId(null);
    setRankedBy(null);
    setSelectedId(null);
    setExpandedId(null);
  }, [placeId, region]);

  // 보내기: 입력한 분위기로 어울리는 고전 시를 추천받고 선택 단계로 넘어간다.
  const handleSend = async () => {
    if (busy || poemsLoading) return;
    setPoemsLoading(true);
    try {
      const res = await fetchPoems(target, prompt);
      setPoems(res.poems);
      setRecommendedId(res.recommended_id);
      setRankedBy(prompt.trim() || null);
      const firstId = res.recommended_id ?? res.poems[0]?.id ?? null;
      setSelectedId(firstId);
      setExpandedId(firstId);  // 추천 시 본문은 펼쳐서 바로 보여준다
    } catch {
      setPoems([]);
      setRecommendedId(null);
      setRankedBy(null);
      setSelectedId(null);
      setExpandedId(null);
    } finally {
      setPoemsLoading(false);
      setStep("choose");
    }
  };

  // 생성: usePoem=true면 고른 시의 정취로, false면 시 없이 프롬프트(+장소)로만.
  const handleGenerate = async (usePoem: boolean) => {
    const el = audioRef.current;
    // autoplay 잠금 해제: 클릭 즉시(동기적으로) 권한 확보 → fetch 후 src 교체해 play()
    if (el) el.play().then(() => el.pause()).catch(() => {});

    setStatus("loading");
    try {
      const { audio_url, generated: gen, fallback_title, license: lic, poem: pm } = await fetchGenerate(target, {
        prompt,
        poemId: usePoem ? selectedId : null,
        usePoem,
      });
      if (!audio_url) { setStatus("error"); return; }
      setAudioUrl(audio_url);
      setGenerated(gen !== false);
      setFallbackTitle(fallback_title ?? "");
      setLicense(lic ?? null);
      setUsedPoem(pm ?? null);
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

  const restart = () => {
    setStatus("idle");
    setAudioUrl(null);
    setUsedPoem(null);
    setStep(poems.length > 0 ? "choose" : "input");
  };

  return (
    <div className="card border-dashed border-gold/30 bg-paper/40">
      <div>
        <div className="font-serif font-semibold text-base">
          {region ? `${regionLabel ?? "이 권역"}의 소리로 맞춤 BGM 생성` : "맞춤 BGM 생성"}
        </div>
        <div className="text-xs text-stone-500 mt-0.5">
          원하는 분위기를 적어 보내면, 어울리는 고전 시를 추천해 드려요.
        </div>
      </div>

      {/* ── 1단계: 분위기 입력 → 보내기 ── */}
      {status !== "done" && step === "input" && (
        <div className="mt-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value.slice(0, MAX_PROMPT))}
            disabled={poemsLoading}
            rows={2}
            placeholder="원하는 분위기를 적어 보세요 (자세하고 섬세한 묘사일수록 더 좋은 곡이 생성됩니다) — 예: 비 오는 밤, 느리고 쓸쓸한 대금 가락"
            className="w-full text-xs rounded-lg border border-stone-200 bg-white px-2.5 py-1.5
                       placeholder:text-stone-400 focus:border-gold focus:ring-2 focus:ring-gold/30 focus:outline-none resize-none transition-colors"
          />
          <div className="flex justify-between text-[10px] text-stone-400 mt-0.5">
            <span>
              {region
                ? "짧게 쓰면 권역의 소리 색이, 길고 자세할수록 내 묘사가 곡을 주도해요."
                : ""}
            </span>
            <span>{prompt.length}/{MAX_PROMPT}</span>
          </div>
          <button
            className="btn-primary text-sm mt-2 w-full disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={poemsLoading}
            onClick={handleSend}
          >
            {poemsLoading ? "어울리는 시 찾는 중…" : "보내기"}
          </button>
        </div>
      )}

      {/* ── 2단계: 추천된 시 + "시를 쓸까요?" 선택 ── */}
      {status !== "done" && step === "choose" && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-serif text-ink">
              {rankedBy
                ? <>「{rankedBy.length > 16 ? rankedBy.slice(0, 16) + "…" : rankedBy}」에 어울리는 고전 시예요.</>
                : <>이 장소에 어울리는 고전 시예요.</>}
            </p>
            <button
              type="button"
              onClick={() => setStep("input")}
              className="text-[11px] text-stone-400 hover:text-jade underline underline-offset-2 shrink-0"
            >
              ↺ 다시 입력
            </button>
          </div>
          <p className="section-label mb-2 block">시의 정취로 BGM을 만들어 볼까요?</p>

          {poems.length > 0 ? (
            <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
              {poems.map((p) => {
                const isSel = selectedId === p.id;
                const isOpen = expandedId === p.id;
                return (
                  <div
                    key={p.id}
                    className={`rounded-lg border transition-colors ${isSel ? "border-gold bg-gold/5" : "border-stone-200"}`}
                  >
                    <div className="flex items-center gap-2 p-2">
                      <button
                        type="button"
                        aria-label="이 시 선택"
                        disabled={busy}
                        onClick={() => setSelectedId(p.id)}
                        className={`w-3.5 h-3.5 rounded-full border shrink-0 transition-colors ${isSel ? "border-gold bg-gold" : "border-stone-300 hover:border-gold"}`}
                      />
                      {/* 제목 클릭 → 본문 펼치기/접기 */}
                      <button
                        type="button"
                        onClick={() => setExpandedId(isOpen ? null : p.id)}
                        className="flex-1 text-left min-w-0 flex items-baseline gap-1.5"
                      >
                        <span className="font-serif text-sm text-ink truncate">「{p.title}」</span>
                        <span className="text-xs text-stone-500 shrink-0">{p.author}</span>
                      </button>
                      {p.id === recommendedId && (
                        <span className="badge bg-gold/15 text-gold shrink-0">추천</span>
                      )}
                      <span className="text-[10px] text-stone-300 shrink-0 select-none">{isOpen ? "접기" : "본문"}</span>
                    </div>
                    {isOpen && (
                      <div className="px-3 pb-3">
                        <div className="rule-gold mb-2" />
                        <p className="font-serif text-sm leading-relaxed text-ink whitespace-pre-line">
                          {p.text.split(" / ").join("\n")}
                        </p>
                        <p className="mt-2 text-[10px] text-stone-400">
                          — {p.author} · {p.era} · {p.form} · {p.license}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-stone-400">추천할 고전 시를 찾지 못했어요. 내가 적은 분위기로만 생성할 수 있어요.</p>
          )}

          {/* 시를 쓸지 말지 — 예 / 아니요 */}
          <div className="mt-3 flex flex-col sm:flex-row gap-2">
            <button
              className="btn-primary text-sm flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={busy || poems.length === 0 || !selectedId}
              onClick={() => handleGenerate(true)}
            >
              {busy ? "생성 중…" : "네, 이 시의 감성을 더해 만들기"}
            </button>
            <button
              className="btn-secondary text-sm flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={busy}
              onClick={() => handleGenerate(false)}
            >
              아니요, 내가 적은 분위기대로만 만들기
            </button>
          </div>
          <p className="mt-1.5 text-[10px] text-stone-400">
            ‘네’를 고르면 선택한 시의 정취에 내가 쓴 분위기가 더해지고, ‘아니요’는 입력한 분위기(+{region ? "권역" : "장소"} 정보)로만 생성합니다.
          </p>
        </div>
      )}

      {/* audio 엘리먼트는 항상 마운트 — 클릭 시점에 ref가 살아있어야 autoplay unlock이 동작한다 */}
      <div className={status === "done" && audioUrl ? "mt-3" : "hidden"}>
        {/* 영감을 준 고전 시 — 공개(만료) 원문. 생성 BGM의 분위기 출처를 함께 보여준다. */}
        {usedPoem && (
          <div className="mb-3 rounded-xl border border-gold/30 bg-paper/40 p-4">
            <p className="section-label mb-2 block">
              {generated ? "이 시에서 영감을 받은 BGM" : "이 장소와 어울리는 고전 시"}
            </p>
            <p className="font-serif text-sm leading-relaxed text-ink whitespace-pre-line">
              {usedPoem.text.split(" / ").join("\n")}
            </p>
            <div className="rule-gold my-3" />
            <div className="flex items-center justify-between text-xs">
              <span className="text-stone-600">— {usedPoem.author} · {usedPoem.era}</span>
              <span className="text-stone-400">{usedPoem.form}</span>
            </div>
            <p className="mt-1 text-[10px] text-stone-400">
              「{usedPoem.title}」 · {usedPoem.source} · {usedPoem.license}
            </p>
          </div>
        )}
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
              {copied ? "✓ 복사됨" : "출처 문구 복사"}
            </button>
            <p className="mt-1.5 text-[10px] text-stone-400 leading-relaxed">
              {license.personal_use_only
                ? "※ AI 생성물은 ElevenLabs 약관을 따릅니다. 위 문구로 출처를 표시하고 개인적 용도로 사용하세요. 상업적 이용은 별도 권리 확인이 필요합니다."
                : "※ 출처표시는 법적 의무입니다. 위 문구를 영상 더보기란(크레딧)에 그대로 붙여 넣어 주세요."}
            </p>
          </div>
        )}

        <button
          onClick={restart}
          className="btn-ghost text-xs mt-2 w-full"
        >
          ↺ 다시 만들기
        </button>
      </div>
      {status === "error" && (
        <p className="mt-2 text-xs text-red-500">생성 실패. 인터넷 연결이나 API 키를 확인하세요.</p>
      )}
    </div>
  );
}
