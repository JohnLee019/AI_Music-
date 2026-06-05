"""임베딩 로드/생성 + 코사인 유사도.

두 가지 임베딩 백엔드를 지원한다 (AGENTS.md §3):
  1. Hugging Face Inference API (`jhgan/ko-sroberta-multitask`, 768차원) — HF_API_KEY 있을 때.
  2. 키워드 매칭 폴백 (KEYWORD_DIMS, 34차원) — 키 없거나 HF 실패 시.

빌드(prep)와 런타임이 같은 함수를 쓰므로 벡터 공간이 일치한다.
런타임 매칭은 numpy 코사인만 사용하므로 차원과 무관하게 동작한다.
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── 임베딩 백엔드 설정 ────────────────────────────────
HF_MODEL = "jhgan/ko-sroberta-multitask"
# 구 endpoint(api-inference.huggingface.co)는 폐기됨. 현재는 router 경유.
HF_URL = (
    f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
    "/pipeline/feature-extraction"
)
HF_TIMEOUT_SEC = 60
HF_DIM = 768

KEYWORD_MODEL = "keyword-match-v1"
# 키워드 폴백 공간 (차원 인덱스 고정). 텍스트에 단어가 등장하면 1, 아니면 0 → L2 정규화.
KEYWORD_DIMS = [
    "왕실", "궁중", "의례", "장엄", "정제",            # 0-4 궁궐
    "민속", "마을", "농촌", "공동체", "활기",           # 5-9 민속
    "전통", "역사", "문화유산", "격식", "고요",          # 10-14 공통
    "정악", "궁중음악", "관현악",                        # 15-17 정악
    "민요", "농악", "사물놀이", "풍물",                  # 18-21 민속악
    "판소리", "산조", "가곡", "독주",                    # 22-25 성악/독주
    "경기", "영남", "호남", "강원", "충청", "제주",      # 26-31 권역
    "아리랑", "타령",                                    # 32-33 민요 키워드
]


# ── 임베딩 텍스트 레시피 (AGENTS.md §5.3, 변경 시 양쪽 코퍼스 재생성) ──
def place_recipe(place: dict[str, Any]) -> str:
    kws = ",".join(place.get("cultural_keywords", []))
    return f"{place.get('name','')}. {place.get('description','')} 키워드: {kws}"


def track_recipe(track: dict[str, Any]) -> str:
    instruments = ",".join(track.get("instruments", []))
    mood = ",".join(track.get("mood", []))
    return (
        f"{track.get('title','')}. {track.get('genre','')}. "
        f"악기: {instruments}. 분위기: {mood}. {track.get('description','')}"
    )


EMBED_TEXT_RECIPE = (
    "place: '{name}. {description} 키워드: {cultural_keywords}' / "
    "track: '{title}. {genre}. 악기: {instruments}. 분위기: {mood}. {description}'"
)


# ── HF Inference 호출 ─────────────────────────────────
def _hf_key() -> str:
    return os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or ""


def _pool_one(item: Any) -> np.ndarray:
    """단일 입력 응답을 768차원 벡터로 풀링한다.

    sentence-transformers 모델은 보통 풀링된 [768] 또는 [tokens][768]을 준다.
    """
    a = np.array(item, dtype=np.float32)
    if a.ndim == 1:
        return a
    if a.ndim == 2:  # 토큰 단위 → 평균 풀링
        return a.mean(axis=0)
    raise ValueError(f"예상치 못한 임베딩 shape: {a.shape}")


def embed_remote(texts: list[str], key: str) -> list[list[float]]:
    """HF Inference API로 텍스트 리스트를 임베딩한다. 실패 시 예외를 던진다."""
    import httpx  # 지연 임포트 (런타임 의존성 최소화)

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"inputs": texts, "options": {"wait_for_model": True}}
    with httpx.Client(timeout=HF_TIMEOUT_SEC) as client:
        resp = client.post(HF_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # data는 보통 [N][768] 또는 [N][tokens][768]. ragged면 항목별 풀링.
    try:
        arr = np.array(data, dtype=np.float32)
        if arr.ndim == 2:
            vecs = [arr[i] for i in range(arr.shape[0])]
        elif arr.ndim == 3:
            vecs = [arr[i].mean(axis=0) for i in range(arr.shape[0])]
        else:
            raise ValueError(f"예상치 못한 배치 shape: {arr.shape}")
    except (ValueError, TypeError):
        vecs = [_pool_one(item) for item in data]

    return [[round(float(x), 6) for x in v] for v in vecs]


def embed_keyword(text: str) -> list[float]:
    """키워드 매칭 기반 폴백 임베딩 (외부 의존 없음)."""
    vec = [1.0 if dim in text else 0.0 for dim in KEYWORD_DIMS]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


def embed_corpus(texts: list[str]) -> tuple[list[list[float]], str, int]:
    """코퍼스 전체를 임베딩한다. 모드(HF vs 키워드)를 1회 결정해 일관성을 보장한다.

    Returns: (벡터 리스트, embedding_model 이름, embedding_dim)
    """
    key = _hf_key()
    if key:
        try:
            vecs = embed_remote(texts, key)
            dim = len(vecs[0]) if vecs else HF_DIM
            print(f"[embeddings] HF Inference 사용 — {len(texts)}건, {dim}차원")
            return vecs, HF_MODEL, dim
        except Exception as exc:  # noqa: BLE001
            print(f"[embeddings] HF 실패 → 키워드 폴백으로 전환: {type(exc).__name__}: {exc}")
    else:
        print("[embeddings] HF_API_KEY 없음 → 키워드 폴백 사용")

    vecs = [embed_keyword(t) for t in texts]
    return vecs, KEYWORD_MODEL, len(KEYWORD_DIMS)


def embed_query(text: str) -> list[float]:
    """런타임 단일 쿼리(자유 시놉시스) 임베딩. 실패 시 키워드 폴백."""
    key = _hf_key()
    if key:
        try:
            return embed_remote([text], key)[0]
        except Exception as exc:  # noqa: BLE001
            print(f"[embeddings] 런타임 HF 실패 → 키워드 폴백: {exc}")
    return embed_keyword(text)


# ── 코사인 유사도 ─────────────────────────────────────
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도 [-1, 1]. 차원 무관."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    if va.shape != vb.shape or va.size == 0:
        return 0.0
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ── 데이터 로드 (dict 포맷 + 메타데이터) ───────────────
def _load_payload(filename: str, list_key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """{embedding_model, embedding_dim, <list_key>: [...]} 또는 구형 list 포맷을 모두 로드.

    Returns: (레코드 리스트, 파일 레벨 메타데이터)
    """
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # 구형 포맷 (메타 없음)
        return data, {}
    meta = {k: v for k, v in data.items() if k != list_key}
    return data.get(list_key, []), meta


def load_places() -> list[dict[str, Any]]:
    records, _ = _load_payload("places.json", "places")
    return records


def load_tracks() -> list[dict[str, Any]]:
    records, _ = _load_payload("tracks.json", "tracks")
    return records


def assert_embedding_consistency() -> None:
    """places·tracks 임베딩 차원이 같은지 검증 (AGENTS.md §3 일관성 가드)."""
    _, pmeta = _load_payload("places.json", "places")
    _, tmeta = _load_payload("tracks.json", "tracks")
    pdim, tdim = pmeta.get("embedding_dim"), tmeta.get("embedding_dim")
    if pdim is not None and tdim is not None and pdim != tdim:
        raise AssertionError(
            f"임베딩 차원 불일치: places={pdim}, tracks={tdim}. "
            "generate_data.py를 한 번에 재실행해 코퍼스를 동기화하세요."
        )


def load_reasoning() -> dict[str, str]:
    """사전 생성된 근거 텍스트 로드. 파일이 없거나 손상돼도 데모는 멈추지 않는다
    (main.py 가 메타데이터 템플릿 근거로 폴백한다 — AGENTS.md §2)."""
    path = os.path.join(DATA_DIR, "reasoning.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
