"""
히어로 조합 근거를 LLM으로 사전 생성해 reasoning.json에 저장한다.
- prep 단계 1회성 스크립트 (AGENTS.md §4.5, §2: 런타임 호출 아님)
- 환경변수 LLM_API_KEY / LLM_PROVIDER (openai|anthropic) 로 provider-agnostic 동작
- 키/모델 미설정 시 템플릿 근거로 자동 대체 (폴백 → 런타임과 동일 품질 보장)

실행:
    cd backend
    python prep/generate_reasoning.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# backend/ 를 sys.path에 추가 (embeddings, rules 등 임포트용)
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(Path(__file__).parent.parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PLACES_PATH = DATA_DIR / "places.json"
TRACKS_PATH = DATA_DIR / "tracks.json"
REASONING_PATH = DATA_DIR / "reasoning.json"

# 히어로 조합: place_id → [track_id, ...]
# 매칭 엔진 결과를 기반으로 미리 정의 (상위 5곡 × 4 장소 = 최대 20개 근거)
HERO_PLACE_IDS = ["gyeongbokgung", "hahoe", "jeonju_hanok", "namdaemun"]

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY  = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")  # 저비용 기본값


# ── 데이터 로드 ────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_top_tracks(place: dict, tracks: list[dict], top_n: int = 5) -> list[dict]:
    """매칭 엔진을 이용해 장소에 맞는 상위 트랙을 구한다."""
    from embeddings import cosine_similarity
    from rules import TYPE_GENRE_WEIGHTS

    place_region = place.get("music_region", "")
    place_type   = place.get("type", "")
    place_emb    = place.get("embedding", [])

    genre_weights = TYPE_GENRE_WEIGHTS.get(place_type, {})

    scored = []
    for t in tracks:
        r = 1.0 if place_region == t.get("region", "") else 0.0
        g_score = max(
            genre_weights.get(t.get("genre", ""), 0.0),
            genre_weights.get(t.get("sub_genre", ""), 0.0),
        )
        s_raw = cosine_similarity(place_emb, t.get("embedding", []))
        s = (s_raw + 1) / 2
        kw = set(place.get("cultural_keywords", []))
        tags = set(t.get("instruments", [])) | set(t.get("mood", []))
        tag = len(kw & tags) / max(len(kw), len(tags), 1)
        score = 0.30 * r + 0.25 * g_score + 0.30 * s + 0.15 * tag
        scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:top_n]]


# ── 템플릿 폴백 근거 ────────────────────────────────────────────────────────────

def _template_reasoning(place: dict, track: dict) -> str:
    genre  = track.get("sub_genre") or track.get("genre", "전통음악")
    region = track.get("region", "")
    moods  = ", ".join(track.get("mood", [])[:2])
    kws    = ", ".join(place.get("cultural_keywords", [])[:3])
    return (
        f"{place['name']}의 {place['type']} 특성에 맞추어, "
        f"{region} 권역의 {genre}인 «{track['title']}»을 선곡했습니다. "
        f"장소의 문화 키워드({kws})와 음악의 분위기({moods})가 어울립니다."
    )


# ── LLM 근거 생성 ──────────────────────────────────────────────────────────────

def _build_prompt(place: dict, track: dict) -> str:
    return (
        "당신은 국악 큐레이터입니다. 아래 장소와 음악의 연결 근거를 한국어로 2~3문장으로 설명하세요.\n"
        "• 장소: {place_name} ({place_type}, {place_region}권역)\n"
        "  문화 키워드: {keywords}\n"
        "• 음악: «{track_title}» — {genre}, 악기: {instruments}, 분위기: {mood}\n"
        "설명은 \"~입니다\" 체로 끝내며, 장소의 역사·문화 맥락과 음악의 특성을 연결하세요."
    ).format(
        place_name=place["name"],
        place_type=place.get("type", ""),
        place_region=place.get("music_region", ""),
        keywords=", ".join(place.get("cultural_keywords", [])[:4]),
        track_title=track["title"],
        genre=track.get("sub_genre") or track.get("genre", ""),
        instruments=", ".join(track.get("instruments", [])[:4]),
        mood=", ".join(track.get("mood", [])[:3]),
    )


def _call_llm_openai(prompt: str) -> str:
    import httpx
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.7,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_llm_anthropic(prompt: str) -> str:
    import httpx
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": LLM_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": LLM_MODEL if "claude" in LLM_MODEL else "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


def _generate_reasoning(place: dict, track: dict) -> str:
    if not LLM_API_KEY:
        return _template_reasoning(place, track)
    prompt = _build_prompt(place, track)
    try:
        if LLM_PROVIDER == "anthropic":
            return _call_llm_anthropic(prompt)
        return _call_llm_openai(prompt)
    except Exception as e:
        print(f"  ⚠ LLM 실패 ({e}), 템플릿 폴백 사용")
        return _template_reasoning(place, track)


# ── 메인 ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not PLACES_PATH.exists() or not TRACKS_PATH.exists():
        print("❌ places.json / tracks.json 없음 — generate_data.py 먼저 실행하세요.")
        sys.exit(1)

    places_data = _load_json(PLACES_PATH)
    tracks_data = _load_json(TRACKS_PATH)
    places: list[dict] = places_data.get("places", places_data if isinstance(places_data, list) else [])
    tracks: list[dict] = tracks_data.get("tracks", tracks_data if isinstance(tracks_data, list) else [])

    # 기존 reasoning.json 로드 (증분 업데이트)
    existing: dict[str, str] = {}
    if REASONING_PATH.exists():
        try:
            existing = json.loads(REASONING_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    reasoning: dict[str, str] = dict(existing)

    mode = "LLM" if LLM_API_KEY else "템플릿"
    print(f"근거 생성 모드: {mode} (provider={LLM_PROVIDER}, model={LLM_MODEL})")
    print(f"장소 {len(places)}곳 × 상위 5곡 조합 처리 중…\n")

    hero_places = [p for p in places if p["id"] in HERO_PLACE_IDS] or places

    for place in hero_places:
        top_tracks = _get_top_tracks(place, tracks, top_n=5)
        for track in top_tracks:
            key = f"{place['id']}:{track['id']}"
            if key in reasoning:
                print(f"  ↩ 기존 {key}")
                continue
            print(f"  ✍ {key}")
            reasoning[key] = _generate_reasoning(place, track)
            if LLM_API_KEY:
                time.sleep(0.3)  # rate-limit 회피

    REASONING_PATH.write_text(json.dumps(reasoning, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {REASONING_PATH} — {len(reasoning)}개 근거 저장")


if __name__ == "__main__":
    main()
