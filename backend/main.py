"""GugakPlace FastAPI 엔트리포인트."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from embeddings import (  # noqa: E402
    assert_embedding_consistency,
    cosine_similarity,
    embed_query,
    load_places,
    load_reasoning,
    load_tracks,
)
from generation import generate_bgm  # noqa: E402
from licensing import annotate_track, filter_by_use_case  # noqa: E402
from matching import match  # noqa: E402

# ── 앱 시작 시 데이터 로드 ────────────────────────────
_places: list[dict[str, Any]] = []
_tracks: list[dict[str, Any]] = []
_reasoning: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _places, _tracks, _reasoning
    assert_embedding_consistency()  # places·tracks 임베딩 차원 일치 검증 (AGENTS.md §3)
    _places = load_places()
    _tracks = load_tracks()
    _reasoning = load_reasoning()
    yield


# 매칭 결과로 반환할 상위 트랙 개수 (AGENTS.md §9: 매직 넘버 금지).
TOP_N_TRACKS = 5

app = FastAPI(title="GugakPlace API", version="0.1.0", lifespan=lifespan)

# ── CORS ────────────────────────────────────────────
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5174", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 오디오 정적 파일 서빙 ────────────────────────────
_audio_dir = os.path.join(os.path.dirname(__file__), "..", "data", "audio")
os.makedirs(_audio_dir, exist_ok=True)
app.mount("/audio", StaticFiles(directory=_audio_dir), name="audio")


# ── 스키마 ───────────────────────────────────────────
class MatchRequest(BaseModel):
    # place_id(히어로 경로) 또는 query_text(자유 시놉시스 경로) 중 하나는 있어야 한다.
    place_id: str | None = None
    query_text: str | None = None
    use_case: str = "listen"  # "listen" | "creator" | "place_bgm"


class GenerateRequest(BaseModel):
    place_id: str


# ── 헬퍼 ─────────────────────────────────────────────
def _get_place(place_id: str) -> dict[str, Any]:
    for p in _places:
        if p["id"] == place_id:
            return p
    raise HTTPException(status_code=404, detail=f"장소를 찾을 수 없습니다: {place_id}")


def _build_reasoning(place_id: str, track_id: str) -> str:
    key = f"{place_id}:{track_id}"
    if key in _reasoning:
        return _reasoning[key]
    # 템플릿 근거 (LLM 없이)
    place = _get_place(place_id)
    track = next((t for t in _tracks if t["id"] == track_id), {})
    genre = track.get("genre", "전통음악")
    sub = track.get("sub_genre", "")
    region = track.get("region", "")
    return (
        f"{place['name']}의 {place['type']} 특성에 맞추어, "
        f"{region} 권역의 {sub or genre}인 «{track.get('title', '')}»을 선곡했습니다. "
        f"장소의 문화 키워드({', '.join(place.get('cultural_keywords', [])[:3])})와 "
        f"음악의 분위기({', '.join(track.get('mood', [])[:2])})가 잘 어울립니다."
    )


def _build_query_reasoning(query_text: str, track: dict[str, Any]) -> str:
    """자유 텍스트 입력에 대한 템플릿 근거 (의미 유사도 기반)."""
    semantic = track.get("score_detail", {}).get("semantic", 0.0)
    genre = track.get("sub_genre") or track.get("genre", "전통음악")
    mood = ", ".join(track.get("mood", [])[:2])
    snippet = query_text if len(query_text) <= 40 else query_text[:40] + "…"
    return (
        f"입력하신 «{snippet}»의 분위기와 {genre} «{track.get('title', '')}»의 "
        f"의미적 유사도가 높습니다(유사도 {semantic:.0%}). "
        f"음악의 분위기({mood})가 요청과 잘 어울립니다."
    )


def _build_query_place(query_text: str) -> dict[str, Any]:
    """자유 텍스트를 매칭 엔진이 쓰는 합성 place 로 만든다.

    지역·유형 신호는 없으므로(빈 값 → 점수 0) 의미 임베딩 + 태그가 매칭을 주도한다
    (AGENTS.md §6: query_text 경로는 의미 임베딩이 핵심, 지역은 생략).
    """
    return {
        "id": "__query__",
        "name": query_text if len(query_text) <= 30 else query_text[:30] + "…",
        "type": "자유 검색",
        "region": "-",
        "music_region": "-",          # 어떤 트랙 region 과도 일치하지 않음 → 지역 점수 0
        "description": "입력하신 텍스트의 의미를 분석해 매칭한 결과입니다.",
        "cultural_keywords": query_text.split(),  # 태그 매칭용 토큰
        "embedding": embed_query(query_text),     # 런타임 HF 임베딩 (실패 시 키워드 폴백)
    }


# ── 엔드포인트 ────────────────────────────────────────
@app.get("/api/places")
def get_places():
    """데모 장소 목록 반환 (임베딩 벡터 제외)."""
    return [
        {k: v for k, v in p.items() if k != "embedding"}
        for p in _places
    ]


# 추천 장소로 보여줄 개수.
SUGGEST_TOP_K = 3


@app.get("/api/places/suggest")
def suggest_places(q: str, k: int = SUGGEST_TOP_K):
    """검색어와 의미가 가까운 보유 장소를 추천한다.

    찾는 장소가 데이터셋에 없을 때(예: '창덕궁') 비슷한 장소(예: '경복궁')를
    임베딩 코사인 유사도로 제안한다. 추가 데이터·LLM 불필요.
    """
    q = (q or "").strip()
    if not q:
        return []
    qvec = embed_query(q)
    scored = [
        (cosine_similarity(qvec, p.get("embedding", [])), p)
        for p in _places
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for sim, p in scored[:max(1, k)]:
        rec = {key: v for key, v in p.items() if key != "embedding"}
        rec["similarity"] = round((sim + 1) / 2, 4)  # [-1,1] → [0,1]
        out.append(rec)
    return out


@app.post("/api/match")
def post_match(body: MatchRequest):
    """place_id(히어로) 또는 query_text(자유 시놉시스) → 점수순 트랙 + 근거."""
    is_query = bool(body.query_text and body.query_text.strip())
    if is_query:
        place = _build_query_place(body.query_text.strip())
    elif body.place_id:
        place = _get_place(body.place_id)
    else:
        raise HTTPException(status_code=422, detail="place_id 또는 query_text가 필요합니다.")

    # 자유 텍스트는 지역·유형 신호가 없으므로 의미·태그 위주로 재정규화 (AGENTS.md §6)
    ranked = match(place, _tracks, weights=(0.0, 0.0, 0.8, 0.2)) if is_query else match(place, _tracks)

    # 라이선스 파생값 주입 후 use_case 필터 적용
    annotated = [annotate_track(t) for t in ranked]
    filtered = filter_by_use_case(annotated, body.use_case)
    top_tracks = filtered[:TOP_N_TRACKS]

    for track in top_tracks:
        if is_query:
            track["reasoning"] = _build_query_reasoning(body.query_text.strip(), track)
        else:
            track["reasoning"] = _build_reasoning(body.place_id, track["id"])

    return {
        "place": {k: v for k, v in place.items() if k != "embedding"},
        "tracks": top_tracks,
    }


@app.post("/api/generate")
async def post_generate(body: GenerateRequest):
    """장소에 맞는 BGM 생성 (보조 기능, 폴백 포함)."""
    place = _get_place(body.place_id)
    ranked = match(place, _tracks)
    # 2차 가공(생성)은 is_derivative_allowed=True 음원만 참조 (AGENTS.md §5.5)
    derivable = [t for t in ranked if t.get("is_derivative_allowed", True)]
    top_track = derivable[0] if derivable else (ranked[0] if ranked else {})
    audio_url = await generate_bgm(place, top_track)
    return {"audio_url": audio_url, "prompt_used": True}


@app.get("/health")
def health():
    return {"status": "ok", "places": len(_places), "tracks": len(_tracks)}
