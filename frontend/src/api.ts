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
  commercial_ok?: boolean;
  derivative_ok?: boolean;
  attribution_text?: string;
  score: number;
  score_detail: ScoreDetail;
  reasoning: string;
}

export type UseCase = "listen" | "creator" | "place_bgm";

export interface MatchResult {
  place: Place;
  tracks: Track[];
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

export async function fetchGenerate(place_id: string): Promise<{ audio_url: string }> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ place_id }),
  });
  if (!res.ok) throw new Error("BGM 생성 실패");
  return res.json();
}
