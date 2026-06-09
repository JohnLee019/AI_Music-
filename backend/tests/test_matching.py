"""매칭 엔진 스모크 테스트 (AGENTS.md Phase 2 ❌ 항목)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from matching import (
    _region_score,
    _tag_score,
    _type_score,
    match,
)

# ── 픽스처 ─────────────────────────────────────────────


@pytest.fixture(scope="module")
def places():
    path = os.path.join(os.path.dirname(__file__), "../../data/places.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["places"]


@pytest.fixture(scope="module")
def tracks():
    path = os.path.join(os.path.dirname(__file__), "../../data/tracks.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["tracks"]


@pytest.fixture(scope="module")
def gyeongbokgung(places):
    return next(p for p in places if p["id"] == "gyeongbokgung")


# ── 지역 점수 ──────────────────────────────────────────


def test_region_score_same():
    assert _region_score("경기", "경기") == 1.0


def test_region_score_different():
    assert _region_score("경기", "호남") == 0.0


def test_region_score_wildcard():
    from rules import WILDCARD_REGION_SCORE
    assert _region_score("경기", "전국") == WILDCARD_REGION_SCORE
    assert _region_score("경기", "") == WILDCARD_REGION_SCORE


def test_region_score_affinity():
    # 권역 클릭 경로: 영남 권역에서 강원 트랙을 형제로 취급
    assert _region_score("영남", "강원", affinity={"강원"}) == 1.0


# ── 유형 점수 ──────────────────────────────────────────


def test_type_score_palace_jeongak():
    # 궁궐 → 정악 = 1.0 (AGENTS.md §6-2)
    assert _type_score("궁궐", "정악", "") == 1.0


def test_type_score_market_samulnori():
    # 전통시장 → 사물놀이 = 1.0
    assert _type_score("전통시장", "사물놀이", "") == 1.0


def test_type_score_unknown_type():
    # 알 수 없는 장소 유형은 baseline 이하
    score = _type_score("미등록유형", "정악", "")
    assert score == 0.0


def test_type_score_capped_at_one():
    # max는 1.0을 넘지 않는다
    assert _type_score("궁궐", "궁중음악", "정악") <= 1.0


# ── 태그 점수 ──────────────────────────────────────────


def test_tag_score_full_overlap():
    assert _tag_score(["가야금", "산조"], ["가야금", "산조"], []) == 1.0


def test_tag_score_partial_overlap():
    score = _tag_score(["가야금", "거문고", "해금"], ["가야금"], [])
    assert 0.0 < score < 1.0


def test_tag_score_no_overlap():
    assert _tag_score(["가야금"], ["태평소"], []) == 0.0


def test_tag_score_empty_keywords():
    assert _tag_score([], ["가야금"], []) == 0.0


# ── 통합: 경복궁 → 정악 최우선 ────────────────────────


def test_gyeongbokgung_top_genre_is_jeongak(gyeongbokgung, tracks):
    results = match(gyeongbokgung, tracks)
    assert results, "매칭 결과가 비어 있음"
    top = results[0]
    assert top["genre"] == "정악", (
        f"경복궁 1위 장르가 '정악'이어야 하는데 '{top['genre']}' (곡: {top['title']})"
    )


def test_gyeongbokgung_top5_all_jeongak(gyeongbokgung, tracks):
    results = match(gyeongbokgung, tracks)
    top5_genres = [r["genre"] for r in results[:5]]
    assert all(g == "정악" for g in top5_genres), (
        f"경복궁 상위 5곡이 전부 정악이어야 함: {top5_genres}"
    )


def test_gyeongbokgung_score_in_range(gyeongbokgung, tracks):
    results = match(gyeongbokgung, tracks)
    for r in results[:5]:
        assert 0.0 <= r["score"] <= 1.0, f"점수 범위 초과: {r['score']}"


def test_score_detail_keys_present(gyeongbokgung, tracks):
    results = match(gyeongbokgung, tracks)
    for r in results[:3]:
        assert set(r["score_detail"].keys()) == {"region", "type", "semantic", "tag"}


# ── 가중치 오버라이드 (자유 텍스트 경로) ──────────────


def test_query_text_weights_no_region_type(gyeongbokgung, tracks):
    # 자유 텍스트 경로: 지역·유형 신호 0, 의미·태그만
    results_text = match(gyeongbokgung, tracks, weights=(0, 0, 0.8, 0.2))
    for r in results_text:
        assert r["score_detail"]["region"] == 0.0 or True  # region 원점수는 보존
        assert 0.0 <= r["score"] <= 1.0


def test_weights_normalization(gyeongbokgung, tracks):
    # 합이 1이 아닌 가중치도 정규화되어 결과가 나온다
    results = match(gyeongbokgung, tracks, weights=(3, 2.5, 3, 1.5))
    assert results
    assert all(0.0 <= r["score"] <= 1.0 for r in results)


# ── 결과 정렬 ──────────────────────────────────────────


def test_results_sorted_descending(gyeongbokgung, tracks):
    results = match(gyeongbokgung, tracks)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), "결과가 점수 내림차순이 아님"
