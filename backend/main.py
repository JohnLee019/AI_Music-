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

from embeddings import load_places, load_reasoning, load_tracks  # noqa: E402
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
    place_id: str
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


# ── 엔드포인트 ────────────────────────────────────────
@app.get("/api/places")
def get_places():
    """데모 장소 목록 반환 (임베딩 벡터 제외)."""
    return [
        {k: v for k, v in p.items() if k != "embedding"}
        for p in _places
    ]


@app.post("/api/match")
def post_match(body: MatchRequest):
    """장소 ID → 점수순 트랙 리스트 + 매칭 근거."""
    place = _get_place(body.place_id)
    ranked = match(place, _tracks)

    # 라이선스 파생값 주입 후 use_case 필터 적용
    annotated = [annotate_track(t) for t in ranked]
    filtered = filter_by_use_case(annotated, body.use_case)
    top_tracks = filtered[:TOP_N_TRACKS]

    for track in top_tracks:
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
