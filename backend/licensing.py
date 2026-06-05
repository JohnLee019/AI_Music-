"""라이선스 → 사용가능범위 파생 (AGENTS.md §5.5)."""
from __future__ import annotations

from typing import Any

# ── 상업 이용 가능 여부 ──────────────────────────────────
_COMMERCIAL_OK: dict[str, bool] = {
    "CC0": True,
    "CC BY": True,
    "CC BY-SA": True,
    "CC BY-ND": True,
    "CC BY-NC": False,
    "CC BY-NC-SA": False,
    "CC BY-NC-ND": False,
    "공공누리 제1유형": True,
    "공공누리 제2유형": False,
    "공공누리 제3유형": True,
    "공공누리 제4유형": False,
}

# ── 2차 저작(편집·변형) 허용 여부 ───────────────────────
_DERIVATIVE_OK: dict[str, bool] = {
    "CC0": True,
    "CC BY": True,
    "CC BY-SA": True,
    "CC BY-ND": False,
    "CC BY-NC": True,
    "CC BY-NC-SA": True,
    "CC BY-NC-ND": False,
    "공공누리 제1유형": True,
    "공공누리 제2유형": True,
    "공공누리 제3유형": False,
    "공공누리 제4유형": False,
}


def commercial_ok(license_type: str) -> bool:
    """license_type → 상업 이용 가능 여부. 알 수 없는 라이선스는 보수적으로 False."""
    return _COMMERCIAL_OK.get(license_type, False)


def derivative_ok(license_type: str) -> bool:
    """license_type → 2차 저작(편집·변형) 허용 여부. 알 수 없는 라이선스는 보수적으로 False."""
    return _DERIVATIVE_OK.get(license_type, False)


def annotate_track(track: dict[str, Any]) -> dict[str, Any]:
    """트랙 dict에 commercial_ok, derivative_ok 필드를 추가해 반환한다 (원본 변경 없음)."""
    lt = track.get("license_type", "")
    return {
        **track,
        "commercial_ok": commercial_ok(lt),
        "derivative_ok": derivative_ok(lt),
    }


def filter_by_use_case(tracks: list[dict[str, Any]], use_case: str) -> list[dict[str, Any]]:
    """
    use_case에 따라 라이선스 부적합 트랙을 제거한다.
    - creator   : 상업 이용 + 2차 저작 모두 허용된 트랙만
    - place_bgm : 상업 이용 허용된 트랙만 (재생은 변경이 아님)
    - listen    : 전체 반환 (비상업 청취·학습)
    """
    if use_case == "creator":
        return [t for t in tracks if t.get("commercial_ok") and t.get("derivative_ok")]
    if use_case == "place_bgm":
        return [t for t in tracks if t.get("commercial_ok")]
    return tracks
