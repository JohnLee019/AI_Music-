"""
하이브리드 문화 맥락 매칭 엔진.
지역 적합도 + 유형 적합도 + 의미 임베딩 유사도 + 태그 적합도 가중 합산.
"""
from __future__ import annotations

from typing import Any

from embeddings import cosine_similarity
from rules import (
    DEFAULT_MUSIC_REGION,
    GENRE_TYPE_BASELINE,
    REGION_MAP,
    TYPE_GENRE_WEIGHTS,
    WILDCARD_REGION_SCORE,
    WILDCARD_REGIONS,
)

# ── 가중치 (튜닝 가능) ─────────────────────────────────
W_REGION = 0.30
W_TYPE = 0.25
W_SEMANTIC = 0.30
W_TAG = 0.15


def _resolve_music_region(region_text: str) -> str:
    """행정구역 텍스트에서 음악 권역을 추출한다."""
    for key, val in REGION_MAP.items():
        if key in region_text:
            return val
    return DEFAULT_MUSIC_REGION


def _region_score(
    place_music_region: str,
    track_region: str,
    affinity: set[str] | None = None,
) -> float:
    """같은 음악 권역이면 1.0. 전국(권역 비특정) 트랙은 중립 부분점수, 그 외 불일치는 0.0.

    affinity: 토리 형제로 동치 취급할 track.region 집합(권역 클릭 경로). 영남처럼
    전용 음원이 없는 권역이 메나리토리 형제(강원) 음원을 권역 일치로 받게 한다.
    """
    if track_region in WILDCARD_REGIONS:
        return WILDCARD_REGION_SCORE
    if affinity and track_region in affinity:
        return 1.0
    return 1.0 if place_music_region == track_region else 0.0


def _type_score(place_type: str, track_genre: str, track_sub_genre: str) -> float:
    """장소 유형 규칙표 기반 장르 적합도. 범용 장르(국악 BGM 등)는 baseline floor 적용."""
    weights = TYPE_GENRE_WEIGHTS.get(place_type, {})
    g1 = weights.get(track_genre, 0.0)
    g2 = weights.get(track_sub_genre, 0.0)
    baseline = GENRE_TYPE_BASELINE.get(track_genre, 0.0)
    return min(1.0, max(g1, g2, baseline))


def _tag_score(cultural_keywords: list[str], track_instruments: list[str], track_mood: list[str]) -> float:
    """장소 cultural_keywords ↔ 트랙 instruments/mood 교집합 비율."""
    kw_set = set(cultural_keywords)
    track_tags = set(track_instruments) | set(track_mood)
    if not kw_set or not track_tags:
        return 0.0
    overlap = kw_set & track_tags
    return len(overlap) / max(len(kw_set), len(track_tags))


def match(
    place: dict[str, Any],
    tracks: list[dict[str, Any]],
    *,
    weights: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """
    place 에 대해 tracks를 점수순 정렬하여 반환한다.
    각 트랙에 score, score_detail 필드를 추가한다.

    weights: (지역, 유형, 의미, 태그) 가중치 오버라이드. 자유 텍스트 검색처럼
    지역·유형 신호가 없을 때 (0, 0, 0.8, 0.2) 등으로 재정규화해 점수 스케일을 맞춘다.
    합이 1이 아니면 정규화한다.
    """
    w_region, w_type, w_semantic, w_tag = weights or (W_REGION, W_TYPE, W_SEMANTIC, W_TAG)
    w_sum = w_region + w_type + w_semantic + w_tag or 1.0
    w_region, w_type, w_semantic, w_tag = (
        w_region / w_sum, w_type / w_sum, w_semantic / w_sum, w_tag / w_sum,
    )

    results = []
    place_region = place.get("music_region", "")
    place_embedding = place.get("embedding", [])
    place_type = place.get("type", "")
    affinity = set(place.get("region_affinity") or [])  # 권역 클릭 경로에서만 채워짐
    for track in tracks:
        r = _region_score(place_region, track.get("region", ""), affinity)
        t = _type_score(place_type, track.get("genre", ""), track.get("sub_genre", ""))
        s = cosine_similarity(place_embedding, track.get("embedding", []))
        # 유사도 범위를 [0, 1]로 정규화 (원래 [-1, 1])
        s_norm = (s + 1) / 2
        g = _tag_score(
            place.get("cultural_keywords", []),
            track.get("instruments", []),
            track.get("mood", []),
        )
        final = w_region * r + w_type * t + w_semantic * s_norm + w_tag * g

        entry = dict(track)
        entry.pop("embedding", None)  # 응답에서 임베딩 벡터 제거
        entry["score"] = round(final, 4)
        entry["score_detail"] = {
            "region": round(r, 4),
            "type": round(t, 4),
            "semantic": round(s_norm, 4),
            "tag": round(g, 4),
        }
        results.append(entry)

    # 1차: 최종 점수 내림차순, 동점이면 의미 유사도 내림차순 (AGENTS.md §6)
    results.sort(key=lambda x: (x["score"], x["score_detail"]["semantic"]), reverse=True)
    return results


def select_diverse(
    ranked: list[dict[str, Any]],
    top_n: int,
    *,
    reserved_genre: str,
    reserved_count: int,
) -> list[dict[str, Any]]:
    """상위 top_n 결과에 특정 장르(reserved_genre, 예: 국악 BGM)를 최소 reserved_count 개 보장한다.

    장소 매칭은 전통 음원(민요·정악)이 지역·유형 점수로 상위를 독점하기 쉬운데,
    크리에이터가 원하는 트렌디한 BGM 도 추천에 함께 노출되도록 슬롯을 예약한다.
    점수 모델 자체는 건드리지 않고(=근거·레이더 그대로) 상위 구성만 다양화한다.
    """
    if reserved_count <= 0 or top_n <= 0:
        return ranked[:top_n]
    reserved = [t for t in ranked if t.get("genre") == reserved_genre]
    others = [t for t in ranked if t.get("genre") != reserved_genre]
    n_res = min(reserved_count, len(reserved), top_n)
    chosen = others[: top_n - n_res] + reserved[:n_res]
    chosen.sort(key=lambda x: (x["score"], x["score_detail"]["semantic"]), reverse=True)
    return chosen
