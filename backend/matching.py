"""
하이브리드 문화 맥락 매칭 엔진.
지역 적합도 + 유형 적합도 + 의미 임베딩 유사도 + 태그 적합도 가중 합산.
"""
from __future__ import annotations

import hashlib
import random
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


# 상위 노출에서 같은 (genre, sub_genre) 묶음의 최대 개수.
# 국악 BGM(전통 배경음악)·국악 샘플(악구)처럼 메타가 거의 같아 임베딩이 뭉치는 묶음이
# 상위를 도배해 "어느 장소나 같은 곡" 처럼 보이는 문제를 막는다.
DIVERSITY_KEY_CAP = 2


def _diversity_key(track: dict[str, Any]) -> tuple[str, str]:
    return (track.get("genre", ""), track.get("sub_genre", ""))


def _pick_capped(
    pool: list[dict[str, Any]],
    n: int,
    cap: int,
    counts: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    """pool(점수순)에서 n개 선택. 같은 diversity_key 는 cap 까지만, 모자라면 완화해 채운다.
    counts 는 호출 간 누적되도록 제자리 갱신한다."""
    chosen: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    for t in pool:
        if len(chosen) >= n:
            break
        k = _diversity_key(t)
        if counts.get(k, 0) < cap:
            chosen.append(t)
            counts[k] = counts.get(k, 0) + 1
        else:
            overflow.append(t)
    # 캡 때문에 슬롯이 남으면 점수순을 유지한 채 넘친 후보로 채운다
    for t in overflow:
        if len(chosen) >= n:
            break
        chosen.append(t)
        counts[_diversity_key(t)] = counts.get(_diversity_key(t), 0) + 1
    return chosen


# 점수가 이 폭 안이면 '사실상 동률'로 보고 장소별로 회전 선택한다.
# (국악 BGM 은 지역·유형 점수가 상수라 상위 8곡이 0.005~0.01 차의 노이즈 동률 → 특정
#  한두 곡이 전 장소 추천을 도배. 동률 구간에서만 장소 시드로 분산해 단조로움을 깬다.)
NEAR_TIE_EPS = 0.01


def _seeded_pick(items: list[dict[str, Any]], n: int, seed: Any) -> list[dict[str, Any]]:
    """동률 후보 items 중 n개를 '장소 시드'로 결정적 선택(장소마다 다르게, 재현 가능)."""
    if n <= 0 or not items:
        return []
    if len(items) <= n:
        return list(items)
    h = int(hashlib.md5(str(seed).encode("utf-8")).hexdigest(), 16) if seed is not None else 0
    idx = list(range(len(items)))
    random.Random(h).shuffle(idx)
    return [items[i] for i in idx[:n]]


def _pick_reserved_rotating(
    pool: list[dict[str, Any]],
    n: int,
    seed: Any,
    eps: float = NEAR_TIE_EPS,
) -> list[dict[str, Any]]:
    """예약 장르(BGM) n개를 고른다. 최상위 점수와 eps 이내인 '동률 구간'에서는 장소 시드로
    회전 선택해 분산하고(특정 BGM 도배 방지), 한 곡이 뚜렷이 앞서면 그 곡을 그대로 유지한다.
    동률 구간이 n보다 작으면 다음 점수 곡으로 채운다."""
    if n <= 0 or not pool:
        return []
    top = pool[0]["score"]
    window = [t for t in pool if top - t["score"] <= eps]
    picked = _seeded_pick(window, min(n, len(window)), seed)
    if len(picked) < n:
        picked_ids = {t.get("id") for t in picked}
        for t in pool:
            if len(picked) >= n:
                break
            if t.get("id") not in picked_ids:
                picked.append(t)
    picked.sort(key=lambda x: (x["score"], x["score_detail"]["semantic"]), reverse=True)
    return picked


def select_diverse(
    ranked: list[dict[str, Any]],
    top_n: int,
    *,
    reserved_genre: str,
    reserved_count: int,
    key_cap: int = DIVERSITY_KEY_CAP,
    seed: Any = None,
) -> list[dict[str, Any]]:
    """상위 top_n 결과를 다양화한다: (1) 특정 장르(reserved_genre, 예: 국악 BGM)를 최소
    reserved_count 개 보장하고, (2) 같은 (genre, sub_genre) 묶음을 key_cap 개로 제한하며,
    (3) 예약 장르의 동률 구간은 seed(장소 id)로 회전 선택해 곡별 도배를 막는다.

    장소 매칭은 전통 음원(민요·정악)이 지역·유형 점수로 상위를 독점하기 쉽고, 반대로
    메타가 똑같은 전국 공용 음원(BGM·샘플)은 어디서나 같은 순위로 떠 추천이 단조로워진다.
    점수 모델 자체는 건드리지 않고(=근거·레이더 그대로) 상위 '구성'만 다양화한다.
    """
    if top_n <= 0:
        return []
    reserved_count = max(0, min(reserved_count, top_n))
    reserved_pool = [t for t in ranked if t.get("genre") == reserved_genre]
    others_pool = [t for t in ranked if t.get("genre") != reserved_genre]

    counts: dict[tuple[str, str], int] = {}
    # 1) 예약 장르(BGM) 슬롯: 동률 구간은 장소 시드로 회전 선택(특정 BGM 도배 방지)
    n_reserved = min(reserved_count, len(reserved_pool), max(0, key_cap))
    reserved_sel = _pick_reserved_rotating(reserved_pool, n_reserved, seed)
    for t in reserved_sel:
        counts[_diversity_key(t)] = counts.get(_diversity_key(t), 0) + 1
    # 2) 나머지 슬롯을 그 외 장르에서 다양성 캡 적용해 채움
    others_sel = _pick_capped(others_pool, top_n - len(reserved_sel), key_cap, counts)
    chosen = reserved_sel + others_sel

    # 3) 캡 때문에 여전히 모자라면 남은 전체(점수순)로 보충
    if len(chosen) < top_n:
        chosen_ids = {t.get("id") for t in chosen}
        for t in ranked:
            if len(chosen) >= top_n:
                break
            if t.get("id") not in chosen_ids:
                chosen.append(t)

    chosen.sort(key=lambda x: (x["score"], x["score_detail"]["semantic"]), reverse=True)
    return chosen
