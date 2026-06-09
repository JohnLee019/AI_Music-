"""GugakPlace FastAPI 엔트리포인트."""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from embeddings import (  # noqa: E402
    assert_embedding_consistency,
    cosine_similarity,
    embed_corpus,
    embed_query,
    load_places,
    load_poems,
    load_reasoning,
    load_regions,
    load_tracks,
    region_recipe,
)
from generation import generate_bgm  # noqa: E402
from licensing import annotate_track, filter_by_use_case  # noqa: E402
from matching import match, select_diverse  # noqa: E402
from poems import candidates_for_place, get_poem, poem_recipe, select_poem, to_display  # noqa: E402
from regions import REGION_PROFILES, get_profile  # noqa: E402

# ── 테스트 실패 시 서비스 차단 ───────────────────────
# None = 통과, str = pytest 출력 (실패 내용)
_test_failure: str | None = None

# ── 앱 시작 시 데이터 로드 ────────────────────────────
_places: list[dict[str, Any]] = []
_tracks: list[dict[str, Any]] = []
_reasoning: dict[str, str] = {}
# 권역 key → 사전계산 임베딩(regions.json). 없으면 런타임 embed_query 로 폴백.
_region_embeddings: dict[str, list[float]] = {}
# 공개(만료) 고전 시 — BGM 생성 시 장소에 어울리는 시를 골라 심상을 프롬프트에 더한다.
_poems: list[dict[str, Any]] = []
# 시 id → 임베딩(시작 시 1회 계산). 사용자 무드 프롬프트와 의미 유사도로 시를 추천하는 데 쓴다.
_poem_embeddings: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _places, _tracks, _reasoning, _region_embeddings, _poems, _poem_embeddings, _test_failure

    # 테스트를 먼저 실행. 하나라도 실패하면 API 전체를 503으로 차단한다.
    _backend_dir = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--tb=short", "-q", "--no-header"],
        capture_output=True,
        text=True,
        cwd=_backend_dir,
    )
    if proc.returncode != 0:
        _test_failure = (proc.stdout + proc.stderr).strip()
        print(f"\n[startup] 테스트 실패 — API 비활성화\n{_test_failure}\n", flush=True)
        yield
        return

    print("[startup] 모든 테스트 통과 — 정상 시작", flush=True)
    assert_embedding_consistency()  # places·tracks·regions 임베딩 차원 일치 검증 (AGENTS.md §3)
    _places = load_places()
    _tracks = load_tracks()
    _reasoning = load_reasoning()
    _region_embeddings = {r["key"]: r["embedding"] for r in load_regions() if r.get("embedding")}
    _poems = load_poems()
    # 시 임베딩 1회 계산(소량) — 프롬프트 기반 추천용. embed_query 와 같은 백엔드라 벡터 공간 일치.
    if _poems:
        vecs, _, _ = embed_corpus([poem_recipe(p) for p in _poems])
        _poem_embeddings = {p["id"]: v for p, v in zip(_poems, vecs)}
    yield


# 매칭 결과로 반환할 상위 트랙 개수 (AGENTS.md §9: 매직 넘버 금지).
TOP_N_TRACKS = 5
# 장소(숏컷) 매칭 시 상위 결과에 보장할 국악 BGM(트렌디) 슬롯 수.
# 전통 음원이 지역·유형 점수로 독점하는 것을 막고 크리에이터용 BGM 도 함께 노출.
BGM_GENRE = "국악 BGM"
BGM_RESERVED_SLOTS = 2

app = FastAPI(title="GugakPlace API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def test_gate(request: Request, call_next):
    """테스트 실패 시 /api/* 요청을 모두 503으로 차단한다."""
    if _test_failure is not None and request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=503,
            content={"detail": "테스트 실패로 서비스가 비활성화되었습니다.", "test_output": _test_failure},
        )
    return await call_next(request)


# ── CORS ────────────────────────────────────────────
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5174", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── 오디오 정적 파일 서빙 ────────────────────────────
_audio_dir = os.path.join(os.path.dirname(__file__), "..", "data", "audio")
os.makedirs(_audio_dir, exist_ok=True)
app.mount("/audio", StaticFiles(directory=_audio_dir), name="audio")


# ── 스키마 ───────────────────────────────────────────
class MatchRequest(BaseModel):
    # place_id(히어로) / query_text(자유 시놉시스) / region(소리 지도 권역 클릭) 중 하나.
    place_id: str | None = None
    query_text: str | None = None
    region: str | None = None
    use_case: str = "listen"  # "listen" | "creator" | "place_bgm"


class GenerateRequest(BaseModel):
    place_id: str
    prompt: str | None = None  # 사용자가 직접 입력하는 BGM 묘사(선택). 장소·매칭곡 정보와 합쳐짐.
    poem_id: str | None = None  # 사용자가 고른 고전 시 id. None=추천 시 사용(use_poem=True일 때).
    use_poem: bool = True       # False=시 없이 프롬프트(+장소)만으로 생성.


# ── 헬퍼 ─────────────────────────────────────────────
def _get_place(place_id: str) -> dict[str, Any]:
    for p in _places:
        if p["id"] == place_id:
            return p
    raise HTTPException(status_code=404, detail=f"장소를 찾을 수 없습니다: {place_id}")


def _audio_available(track: dict[str, Any]) -> bool:
    """로컬에 오디오 파일이 실제로 있는지 검사한다.

    카탈로그(183곡)는 전부 매칭되지만 오디오는 서브셋만 받으므로(§11 리포 용량),
    파일 없는 트랙은 프론트에서 '미리듣기 준비중'으로 표시한다.
    """
    rel = track.get("audio_path", "")
    if not rel:
        return False
    return os.path.exists(os.path.join(_audio_dir, os.path.basename(rel)))


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


def _build_region_place(profile: dict[str, Any], query_text: str | None = None) -> dict[str, Any]:
    """음악 권역 프로필을 매칭 엔진이 쓰는 합성 place 로 만든다.

    query_text 가 있으면(권역 + 시놉시스 결합 경로) 임베딩·태그를 그 무드 텍스트에서
    뽑아 '이 권역 안에서 무드로 검색'한다. 없으면(권역 클릭) regions.json 사전계산
    임베딩(없으면 런타임 embed_query)을 쓴다. region_affinity 로 토리 형제 음원까지
    권역 일치로 받는다(영남↔강원 메나리토리 — regions.py 참조).
    """
    key = profile["key"]
    if query_text:
        embedding = embed_query(query_text)
        keywords = query_text.split()
        snippet = query_text if len(query_text) <= 30 else query_text[:30] + "…"
        description = f"{profile['label']} 권역에서 «{snippet}» 무드로 찾은 결과입니다."
    else:
        embedding = _region_embeddings.get(key) or embed_query(region_recipe(profile))
        keywords = list(profile.get("keywords", []))
        description = profile["description"]
    return {
        "id": f"__region__{key}",
        "name": profile["label"],
        "type": "권역",                       # 장소 유형 규칙(TYPE_GENRE_WEIGHTS) 없음 → 유형 가중 0
        "region": "-",
        "music_region": profile["label"],     # 결과 카드 권역 배지에 표기됨
        "region_affinity": profile.get("region_affinity", []),
        "description": description,
        "cultural_keywords": keywords,        # 태그 매칭용 토큰
        "embedding": embedding,
    }


def _build_region_reasoning(profile: dict[str, Any], track: dict[str, Any]) -> str:
    """권역 클릭 결과의 템플릿 근거 (토리·정서 언급)."""
    sub = track.get("sub_genre") or track.get("genre", "전통음악")
    mood = ", ".join(track.get("mood", [])[:2])
    return (
        f"{profile['label']} 권역의 {profile['tori']} 정서에 맞추어 "
        f"{sub} «{track.get('title', '')}»을 선곡했습니다. "
        f"음악의 분위기({mood})가 이 고장의 소리 결과 잘 어울립니다."
    )


def _build_region_query_reasoning(profile: dict[str, Any], query_text: str, track: dict[str, Any]) -> str:
    """권역 + 시놉시스 결합 결과의 근거 (권역 한정 + 무드 의미 유사도)."""
    semantic = track.get("score_detail", {}).get("semantic", 0.0)
    sub = track.get("sub_genre") or track.get("genre", "전통음악")
    snippet = query_text if len(query_text) <= 30 else query_text[:30] + "…"
    return (
        f"{profile['label']} 권역 안에서 «{snippet}» 무드와 의미가 가까운 "
        f"{sub} «{track.get('title', '')}»을 찾았습니다(유사도 {semantic:.0%})."
    )


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


@app.get("/api/regions")
def get_regions():
    """소리 지도 권역 프로필 목록 (임베딩 제외). 지도 색상·범례·클릭에 사용."""
    return [
        {k: v for k, v in p.items() if k not in ("embedding",)}
        for p in REGION_PROFILES
    ]


@app.post("/api/match")
def post_match(body: MatchRequest):
    """place_id(히어로) / query_text(시놉시스) / region(소리 지도) / region+query_text(권역 내 무드 검색) → 트랙 + 근거."""
    q_text = body.query_text.strip() if (body.query_text and body.query_text.strip()) else None
    is_query = q_text is not None
    is_region = bool(body.region and body.region.strip())
    combined = is_region and is_query  # 권역 클릭 + 시놉시스: 그 권역 안에서 무드로 검색
    region_profile: dict[str, Any] | None = None

    if is_region:
        region_profile = get_profile(body.region.strip())
        if region_profile is None:
            raise HTTPException(status_code=404, detail=f"권역을 찾을 수 없습니다: {body.region}")

    if combined:
        place = _build_region_place(region_profile, query_text=q_text)
    elif is_region:
        place = _build_region_place(region_profile)
    elif is_query:
        place = _build_query_place(q_text)
    elif body.place_id:
        place = _get_place(body.place_id)
    else:
        raise HTTPException(status_code=422, detail="place_id·query_text·region 중 하나가 필요합니다.")

    # 결합(권역+무드): 권역 한정 + 무드 의미가 주도. 자유 텍스트: 의미·태그 위주(AGENTS.md §6).
    # 권역 클릭: 유형 신호 없음 → 지역·의미·태그 위주.
    if combined:
        ranked = match(place, _tracks, weights=(0.25, 0.0, 0.6, 0.15))
    elif is_query:
        ranked = match(place, _tracks, weights=(0.0, 0.0, 0.8, 0.2))
    elif is_region:
        ranked = match(place, _tracks, weights=(0.35, 0.0, 0.45, 0.2))
    else:
        ranked = match(place, _tracks)

    # 라이선스 파생값 주입 후 use_case 필터 적용
    annotated = [annotate_track(t) for t in ranked]
    filtered = filter_by_use_case(annotated, body.use_case)

    # 권역 한정 풀: 해당 권역/토리 형제 민요(region 1.0) + 전국 공용 음원(BGM·샘플, 0.6),
    # 무관한 타 권역 음원(0)은 제외. 결합 경로는 이 풀을 무드 의미순으로 정렬·노출한다.
    region_pool = [t for t in filtered if t.get("score_detail", {}).get("region", 0) > 0]

    if combined:
        top_tracks = region_pool[:TOP_N_TRACKS]        # 권역 안에서 무드 의미순 상위
    elif is_query:
        top_tracks = filtered[:TOP_N_TRACKS]
    else:
        top_tracks = select_diverse(
            filtered, TOP_N_TRACKS,
            reserved_genre=BGM_GENRE, reserved_count=BGM_RESERVED_SLOTS,
            seed=place.get("id") or body.place_id,
        )

    for track in top_tracks:
        track["audio_available"] = _audio_available(track)
        if combined:
            track["reasoning"] = _build_region_query_reasoning(region_profile, q_text, track)
        elif is_query:
            track["reasoning"] = _build_query_reasoning(q_text, track)
        elif is_region:
            track["reasoning"] = _build_region_reasoning(region_profile, track)
        else:
            track["reasoning"] = _build_reasoning(body.place_id, track["id"])

    response: dict[str, Any] = {
        "place": {k: v for k, v in place.items() if k != "embedding"},
        "tracks": top_tracks,
    }

    # 권역 경로(클릭·결합): 추천(top) 외에 '이 권역의 국악 전체'를 함께 반환해 사용자가
    # 전부 둘러보고 장르·라이선스로 필터할 수 있게 한다. 정렬은 match 결과를 그대로 따른다
    # (클릭=토리 정서순, 결합=무드 의미순).
    if is_region:
        for track in region_pool:
            track["audio_available"] = _audio_available(track)
            if combined:
                track.setdefault("reasoning", _build_region_query_reasoning(region_profile, q_text, track))
            else:
                track.setdefault("reasoning", _build_region_reasoning(region_profile, track))
        response["region_tracks"] = region_pool

    return response


@app.get("/api/poems")
def get_place_poems(place_id: str, q: str | None = None):
    """장소에 어울리는 고전 시 후보 + 추천 시 id. 사용자가 직접 골라 BGM 을 생성할 수 있게 한다.

    q(사용자 무드 프롬프트)가 있으면 후보를 q 와의 의미 유사도로 정렬·추천한다
    (없으면 장소·권역 기반 결정론적 추천). poems[0] 이 추천 시.
    각 항목은 표시용 필드(원문 text 포함)라 이름 클릭 시 추가 요청 없이 본문을 펼친다."""
    place = _get_place(place_id)
    cands = candidates_for_place(place, _poems)
    query = (q or "").strip()

    if query:
        # 무드 프롬프트와 의미가 가까운 순으로 추천(권역 후보 안에서). 의미 매칭은 HF 임베딩이 핵심.
        qvec = embed_query(query)
        ordered = sorted(
            cands,
            key=lambda p: cosine_similarity(qvec, _poem_embeddings.get(p.get("id", ""), [])),
            reverse=True,
        )
        rec_id = ordered[0].get("id") if ordered else None
    else:
        rec = select_poem(place, _poems)
        rec_id = rec.get("id") if rec else None
        ordered = sorted(cands, key=lambda p: p.get("id") != rec_id)  # 추천 시를 맨 앞으로

    return {"recommended_id": rec_id, "poems": [to_display(p) for p in ordered]}


@app.post("/api/generate")
async def post_generate(body: GenerateRequest):
    """장소에 맞는 BGM 생성 (보조 기능). 생성 불가 시 실제 재생 가능한 최적 매칭 음원으로 폴백."""
    place = _get_place(body.place_id)
    ranked = match(place, _tracks)
    # 2차 가공(생성)은 is_derivative_allowed=True 음원만 참조 (AGENTS.md §5.5)
    derivable = [t for t in ranked if t.get("is_derivative_allowed", True)]
    # 폴백은 반드시 재생 가능한(다운로드된) 음원이어야 무음/깨짐이 없다 (AGENTS.md §2·§8)
    playable = [t for t in derivable if _audio_available(t)]
    top_track = (playable or derivable or ranked or [{}])[0]

    # 고전 시 결정: use_poem=False 면 시 없이(프롬프트만), poem_id 가 있으면 그 시,
    # 없으면 추천 시. 사용자가 직접 고른 시의 심상을 프롬프트에 더하고 화면에도 보여준다.
    if body.use_poem:
        poem = get_poem(body.poem_id, _poems) if body.poem_id else select_poem(place, _poems)
    else:
        poem = None
    poem_payload = to_display(poem)

    audio_url = await generate_bgm(place, top_track, body.prompt, poem=poem)
    if audio_url:
        # AI 생성물은 CC/공공누리가 아니라 ElevenLabs 약관 적용. 사용자는 출처표시 후
        # 개인적 사용만(상업 권리는 플랜 보유자에게 귀속) — 프론트에서 복사용 크레딧 제공.
        return {
            "audio_url": audio_url,
            "generated": True,
            "prompt_used": True,
            "poem": poem_payload,  # 이 시에서 영감받아 생성됨(프론트 문구로 구분)
            "license": {
                "license_type": "AI 생성 (ElevenLabs Music)",
                "source": "ElevenLabs Music",
                "source_url": "",
                "attribution_text": f"«{place['name']} 맞춤 BGM» — AI 생성(ElevenLabs Music) · GugakPlace",
                "commercial_ok": False,
                "derivative_ok": False,
                "personal_use_only": True,
            },
        }
    # 생성 미지원/실패 → 캐싱본(실제 매칭 음원) 폴백. 카탈로그 음원은 실제 CC/공공누리
    # 라이선스가 있어 출처표시가 법적 의무 → 폴백에도 라이선스 정보를 함께 반환한다.
    annotated = annotate_track(top_track)
    fb_title = top_track.get("title", "")
    return {
        "audio_url": top_track.get("audio_path", ""),
        "generated": False,
        "fallback_title": fb_title,
        "poem": poem_payload,  # 생성 실패(폴백)여도 이 장소와 어울리는 고전 시는 함께 보여준다
        "license": {
            "license_type": top_track.get("license_type", ""),
            "source": top_track.get("source", ""),
            "source_url": top_track.get("source_url", ""),
            "attribution_text": top_track.get("attribution_text")
            or f"«{fb_title}» / {top_track.get('source', '')} / {top_track.get('license_type', '')}",
            "commercial_ok": annotated.get("commercial_ok", False),
            "derivative_ok": annotated.get("derivative_ok", False),
            "personal_use_only": False,
        },
    }


@app.get("/health")
def health():
    if _test_failure is not None:
        return JSONResponse(
            status_code=503,
            content={"status": "test_failure", "test_output": _test_failure},
        )
    return {"status": "ok", "places": len(_places), "tracks": len(_tracks)}
