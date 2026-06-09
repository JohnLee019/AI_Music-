"""라이선스 파생·필터 스모크 테스트 (AGENTS.md Phase 2 ❌ 항목, §5.5)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from licensing import annotate_track, commercial_ok, derivative_ok, filter_by_use_case

# ── commercial_ok ──────────────────────────────────────

@pytest.mark.parametrize("lt,expected", [
    ("공공누리 제1유형", True),
    ("공공누리 제2유형", False),
    ("공공누리 제3유형", True),
    ("공공누리 제4유형", False),
    ("CC0",             True),
    ("CC BY",           True),
    ("CC BY-SA",        True),
    ("CC BY-ND",        True),
    ("CC BY-NC",        False),
    ("CC BY-NC-SA",     False),
    ("CC BY-NC-ND",     False),
    ("알 수 없음",       False),  # 보수적 기본값
])
def test_commercial_ok(lt, expected):
    assert commercial_ok(lt) is expected, f"{lt}: commercial_ok 불일치"


# ── derivative_ok ──────────────────────────────────────


@pytest.mark.parametrize("lt,expected", [
    ("공공누리 제1유형", True),
    ("공공누리 제2유형", True),
    ("공공누리 제3유형", False),
    ("공공누리 제4유형", False),
    ("CC0",             True),
    ("CC BY",           True),
    ("CC BY-SA",        True),
    ("CC BY-ND",        False),
    ("CC BY-NC",        True),
    ("CC BY-NC-SA",     True),
    ("CC BY-NC-ND",     False),
    ("알 수 없음",       False),
])
def test_derivative_ok(lt, expected):
    assert derivative_ok(lt) is expected, f"{lt}: derivative_ok 불일치"


# ── annotate_track ─────────────────────────────────────


def test_annotate_track_adds_fields():
    track = {"id": "t01", "title": "테스트곡", "license_type": "CC BY"}
    result = annotate_track(track)
    assert result["commercial_ok"] is True
    assert result["derivative_ok"] is True


def test_annotate_track_does_not_mutate_original():
    track = {"id": "t01", "license_type": "CC BY"}
    annotate_track(track)
    assert "commercial_ok" not in track


def test_annotate_track_unknown_license():
    result = annotate_track({"license_type": "미확인"})
    assert result["commercial_ok"] is False
    assert result["derivative_ok"] is False


# ── filter_by_use_case ─────────────────────────────────


def _make_tracks():
    return [
        {"id": "t1", "license_type": "공공누리 제1유형", "commercial_ok": True,  "derivative_ok": True},
        {"id": "t2", "license_type": "공공누리 제2유형", "commercial_ok": False, "derivative_ok": True},
        {"id": "t3", "license_type": "공공누리 제3유형", "commercial_ok": True,  "derivative_ok": False},
        {"id": "t4", "license_type": "공공누리 제4유형", "commercial_ok": False, "derivative_ok": False},
        {"id": "t5", "license_type": "CC BY-NC",        "commercial_ok": False, "derivative_ok": True},
    ]


def test_creator_filter_keeps_only_commercial_and_derivative():
    # creator = commercial_ok AND derivative_ok → 제1유형만 통과
    result = filter_by_use_case(_make_tracks(), "creator")
    ids = {t["id"] for t in result}
    assert ids == {"t1"}, f"creator 필터 오통과: {ids}"


def test_creator_filter_removes_noncommercial():
    result = filter_by_use_case(_make_tracks(), "creator")
    assert all(t["commercial_ok"] for t in result)
    assert all(t["derivative_ok"] for t in result)


def test_place_bgm_filter_keeps_commercial():
    # place_bgm = commercial_ok (재생은 변경 아님) → 제1·제3유형 통과
    result = filter_by_use_case(_make_tracks(), "place_bgm")
    ids = {t["id"] for t in result}
    assert ids == {"t1", "t3"}, f"place_bgm 필터 오통과: {ids}"


def test_place_bgm_filter_removes_noncommercial():
    result = filter_by_use_case(_make_tracks(), "place_bgm")
    assert all(t["commercial_ok"] for t in result)


def test_listen_filter_returns_all():
    tracks = _make_tracks()
    result = filter_by_use_case(tracks, "listen")
    assert len(result) == len(tracks), "listen 필터는 전체 반환해야 함"


def test_unknown_use_case_returns_all():
    # 알 수 없는 use_case는 listen과 동일하게 전체 반환
    tracks = _make_tracks()
    result = filter_by_use_case(tracks, "undefined_case")
    assert len(result) == len(tracks)
