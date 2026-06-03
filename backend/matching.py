"""
하이브리드 문화 맥락 매칭 엔진.
지역 적합도 + 유형 적합도 + 의미 임베딩 유사도 + 태그 적합도 가중 합산.
"""
from __future__ import annotations

from typing import Any

from embeddings import cosine_similarity

# ── 가중치 (튜닝 가능) ─────────────────────────────────
W_REGION = 0.30
W_TYPE = 0.25
W_SEMANTIC = 0.30
W_TAG = 0.15

# ── 지역 → 음악 권역 매핑 ─────────────────────────────
REGION_MAP: dict[str, str] = {
    "서울": "경기", "경기": "경기", "인천": "경기",
    "강원": "강원",
    "충청": "충청", "충남": "충청", "충북": "충청", "대전": "충청", "세종": "충청",
    "경상": "영남", "경남": "영남", "경북": "영남", "부산": "영남", "대구": "영남", "울산": "영남",
    "전라": "호남", "전남": "호남", "전북": "호남", "광주": "호남",
    "제주": "제주",
}

# ── 장소 유형 → 선호 장르 가중 ────────────────────────
TYPE_GENRE_WEIGHTS: dict[str, dict[str, float]] = {
    "궁궐":    {"정악": 1.0, "궁중음악": 1.0, "제례음악": 0.8, "가곡": 0.6},
    "서원":    {"정악": 0.9, "가곡": 1.0, "산조": 0.6},
    "사찰":    {"제례음악": 0.8, "정악": 0.7},
    "민속마을": {"민요": 1.0, "농악": 1.0, "사물놀이": 0.8, "무속음악": 0.9},
    "한옥마을": {"판소리": 1.0, "산조": 0.9, "민요": 0.8, "농악": 0.6},
    "전통시장": {"사물놀이": 1.0, "농악": 0.9, "민요": 0.8, "풍물": 0.9},
    "전통마을": {"민요": 0.9, "농악": 0.8, "판소리": 0.7},
}


def _resolve_music_region(region_text: str) -> str:
    """행정구역 텍스트에서 음악 권역을 추출한다."""
    for key, val in REGION_MAP.items():
        if key in region_text:
            return val
    return "기타"


def _region_score(place_music_region: str, track_region: str) -> float:
    """같은 음악 권역이면 1.0, 아니면 0.0."""
    return 1.0 if place_music_region == track_region else 0.0


def _type_score(place_type: str, track_genre: str, track_sub_genre: str) -> float:
    """장소 유형 규칙표 기반 장르 적합도."""
    weights = TYPE_GENRE_WEIGHTS.get(place_type, {})
    g1 = weights.get(track_genre, 0.0)
    g2 = weights.get(track_sub_genre, 0.0)
    return min(1.0, max(g1, g2))


def _tag_score(cultural_keywords: list[str], track_instruments: list[str], track_mood: list[str]) -> float:
    """장소 cultural_keywords ↔ 트랙 instruments/mood 교집합 비율."""
    kw_set = set(cultural_keywords)
    track_tags = set(track_instruments) | set(track_mood)
    if not kw_set or not track_tags:
        return 0.0
    overlap = kw_set & track_tags
    return len(overlap) / max(len(kw_set), len(track_tags))


def match(place: dict[str, Any], tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    place 에 대해 tracks를 점수순 정렬하여 반환한다.
    각 트랙에 score, score_detail 필드를 추가한다.
    """
    results = []
    for track in tracks:
        r = _region_score(place["music_region"], track["region"])
        t = _type_score(place["type"], track.get("genre", ""), track.get("sub_genre", ""))
        s = cosine_similarity(place["embedding"], track["embedding"])
        # 유사도 범위를 [0, 1]로 정규화 (원래 [-1, 1])
        s_norm = (s + 1) / 2
        g = _tag_score(
            place.get("cultural_keywords", []),
            track.get("instruments", []),
            track.get("mood", []),
        )
        final = W_REGION * r + W_TYPE * t + W_SEMANTIC * s_norm + W_TAG * g

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

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
