/** GugakPlace API 클라이언트 */

const BASE = "/api";

export interface Place {
  id: string;
  name: string;
  region: string;
  music_region: string;
  type: string;
  lat?: number;   // 자유 텍스트 검색 결과(합성 place)에는 없음
  lng?: number;
  description: string;
  cultural_keywords: string[];
  similarity?: number;  // 추천 결과에만 존재 (검색어와의 의미 유사도 0~1)
  image_url?: string;
  image_copyright?: string;
}

export interface ScoreDetail {
  region: number;
  type: number;
  semantic: number;
  tag: number;
}

export interface Track {
  id: string;
  title: string;
  genre: string;
  sub_genre: string;
  region: string;
  instruments: string[];
  mood: string[];
  description: string;
  audio_path: string;
  source: string;
  source_url: string;
  license_type: string;
  license_note: string;
  is_derivative_allowed: boolean;
  asset_kind?: string;  // "full_track" | "sample_loop"
  audio_available?: boolean;  // 로컬 오디오 파일 존재 여부 (false면 재생 비활성)
  commercial_ok?: boolean;
  derivative_ok?: boolean;
  attribution_text?: string;
  score: number;
  score_detail: ScoreDetail;
  reasoning: string;
}

export type UseCase = "listen" | "creator" | "place_bgm";

export interface Region {
  key: string;
  label: string;
  tori: string;
  color: string;
  members: string[];
  description: string;
  songs: string[];
}

export interface MatchResult {
  place: Place;
  tracks: Track[];
  // 권역 클릭 결과에만 존재: 이 권역의 국악 전체(추천 외 둘러보기·필터용).
  region_tracks?: Track[];
}

export async function fetchPlaces(): Promise<Place[]> {
  const res = await fetch(`${BASE}/places`);
  if (!res.ok) throw new Error("장소 목록 로드 실패");
  return res.json();
}

/** 검색어와 의미가 가까운 보유 장소 추천 (없는 장소 검색 시 연관 장소 제안). */
export async function fetchPlaceSuggestions(q: string, k = 3): Promise<Place[]> {
  const res = await fetch(`${BASE}/places/suggest?q=${encodeURIComponent(q)}&k=${k}`);
  if (!res.ok) throw new Error("연관 장소 조회 실패");
  return res.json();
}

export async function fetchMatch(place_id: string, use_case: UseCase = "listen"): Promise<MatchResult> {
  const res = await fetch(`${BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ place_id, use_case }),
  });
  if (!res.ok) throw new Error("매칭 요청 실패");
  return res.json();
}

/** 자유 시놉시스·무드 텍스트로 매칭 (런타임 임베딩 경로). */
export async function fetchMatchByText(query_text: string, use_case: UseCase = "listen"): Promise<MatchResult> {
  const res = await fetch(`${BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query_text, use_case }),
  });
  if (!res.ok) throw new Error("매칭 요청 실패");
  return res.json();
}

/** 소리 지도 권역(토리) 프로필 목록 (색상·범례·대표곡). */
export async function fetchRegions(): Promise<Region[]> {
  const res = await fetch(`${BASE}/regions`);
  if (!res.ok) throw new Error("권역 목록 로드 실패");
  return res.json();
}

/** 소리 지도에서 권역을 클릭해 그 고장의 토리에 맞는 음악을 매칭. */
export async function fetchMatchByRegion(region: string, use_case: UseCase = "listen"): Promise<MatchResult> {
  const res = await fetch(`${BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, use_case }),
  });
  if (!res.ok) throw new Error("매칭 요청 실패");
  return res.json();
}

/** 선택한 권역 '안에서' 시놉시스·무드로 검색 (권역 한정 + 의미 매칭). */
export async function fetchMatchByRegionQuery(
  region: string,
  query_text: string,
  use_case: UseCase = "listen",
): Promise<MatchResult> {
  const res = await fetch(`${BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, query_text, use_case }),
  });
  if (!res.ok) throw new Error("매칭 요청 실패");
  return res.json();
}

export interface BgmLicense {
  license_type: string;
  source: string;
  source_url?: string;
  attribution_text: string;  // 복사해 크레딧에 붙여 넣을 출처표시 문구
  commercial_ok: boolean;
  derivative_ok: boolean;
  personal_use_only?: boolean;  // true=AI 생성물(개인적 사용 권장)
}

export interface Poem {
  id: string;
  title: string;
  author: string;
  era: string;
  form: string;          // 시조 / 가사 등
  text: string;          // " / " 로 행이 구분된 원문
  theme_ko?: string;
  source: string;
  source_url?: string;
  license: string;       // Public Domain (원문) 등
}

export interface GenerateResult {
  audio_url: string;
  generated?: boolean;       // true=AI 생성, false=캐싱본(매칭 음원) 폴백
  fallback_title?: string;
  poem?: Poem | null;        // 이 장소에 어울리는 공개 고전 시(생성 영감)
  license?: BgmLicense;
}

/** 장소에 어울리는 고전 시 후보 + 추천 시 id (사용자가 직접 골라 생성). */
export interface PoemList {
  recommended_id: string | null;
  poems: Poem[];  // 추천 시가 맨 앞
}

/** BGM 생성·시 추천 대상 — 실제 장소(placeId) 또는 소리 지도 권역(region key) 중 하나. */
export interface GenerateTarget {
  placeId?: string;
  region?: string;
}

/** q(무드 프롬프트)를 주면 그 분위기와 의미가 가까운 순으로 추천·정렬한다. */
export async function fetchPoems(target: GenerateTarget, q?: string): Promise<PoemList> {
  const params = new URLSearchParams();
  if (target.placeId) params.set("place_id", target.placeId);
  if (target.region) params.set("region", target.region);
  if (q && q.trim()) params.set("q", q.trim());
  const res = await fetch(`${BASE}/poems?${params.toString()}`);
  if (!res.ok) throw new Error("고전 시 목록 로드 실패");
  return res.json();
}

export interface GenerateOptions {
  prompt?: string;
  poemId?: string | null;   // 고른 시 id (usePoem=true일 때). 없으면 추천 시.
  usePoem?: boolean;        // false=시 없이 프롬프트만으로 생성 (기본 true)
}

export async function fetchGenerate(target: GenerateTarget, opts: GenerateOptions = {}): Promise<GenerateResult> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      place_id: target.placeId,
      region: target.region,
      prompt: opts.prompt?.trim() || undefined,
      poem_id: opts.poemId ?? undefined,
      use_poem: opts.usePoem ?? true,
    }),
  });
  if (!res.ok) throw new Error("BGM 생성 실패");
  return res.json();
}
