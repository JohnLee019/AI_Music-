/** GugakPlace API 클라이언트 */

const BASE = "/api";

export interface Place {
  id: string;
  name: string;
  region: string;
  music_region: string;
  type: string;
  lat: number;
  lng: number;
  description: string;
  cultural_keywords: string[];
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

export async function fetchMatch(place_id: string, use_case: UseCase = "listen"): Promise<MatchResult> {
  const res = await fetch(`${BASE}/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ place_id, use_case }),
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
