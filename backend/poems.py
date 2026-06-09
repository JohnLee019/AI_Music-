"""
고전 시(시조·가사) 선택 — 장소/권역에 어울리는 공개(저작권 만료) 고전 시를 고른다.

BGM 생성 시 시의 심상(imagery_en)을 음악 프롬프트에 더해 '시에서 영감받은' 국악
BGM 을 만든다(generation.build_prompt). 모든 시는 원문 저작권이 만료된 전근대 작품이며,
원문 그대로만 수록한다(현대 편집·주석본 아님).

선택은 place id 로 시드해 같은 장소가 항상 같은 시를 받도록 결정론적이다
(matching.select_diverse 의 seed 패턴과 동일한 취지).
"""
from __future__ import annotations

import hashlib
from typing import Any

from regions import PLACE_REGION_GROUP

# 프론트로 내보낼 표시용 필드(내부 태그 region_keys·place_types·imagery_en 은 제외).
# id 는 사용자가 시를 직접 고를 때(선택 → 생성) 필요해 포함한다.
DISPLAY_FIELDS = ("id", "title", "author", "era", "form", "text", "theme_ko", "source", "source_url", "license")


def poem_recipe(poem: dict[str, Any]) -> str:
    """시를 임베딩할 한국어 텍스트(제목·정서·원문). 사용자 무드 프롬프트와 의미 비교용."""
    return f"{poem.get('title', '')}. {poem.get('theme_ko', '')}. {poem.get('text', '')}"


def _seeded_index(seed: str, n: int) -> int:
    """seed 문자열 → [0, n) 결정론적 인덱스."""
    if n <= 0:
        return 0
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return int(digest, 16) % n


def _region_key_for_place(place: dict[str, Any]) -> str | None:
    """장소가 속한 권역 key. 합성 권역 place(__region__<key>)는 그 key 를 직접 쓴다."""
    pid = place.get("id", "")
    prefix = "__region__"
    if pid.startswith(prefix):
        return pid[len(prefix):]
    return PLACE_REGION_GROUP.get(place.get("music_region", ""))


def select_poem(place: dict[str, Any], poems: list[dict[str, Any]]) -> dict[str, Any] | None:
    """장소에 어울리는 고전 시 1편을 결정론적으로 고른다.

    우선순위: 같은 권역(region_keys 포함) → 전국 공용(region_keys 빈 배열) → 전체.
    후보가 없으면 None(자유 검색 등 권역 정보가 없으면 공용 풀에서 고른다).
    """
    if not poems:
        return None
    region_key = _region_key_for_place(place)
    regional = [p for p in poems if region_key and region_key in p.get("region_keys", [])]
    universal = [p for p in poems if not p.get("region_keys")]
    pool = regional or universal or poems
    seed = place.get("id") or place.get("name") or ""
    return pool[_seeded_index(seed, len(pool))]


def candidates_for_place(place: dict[str, Any], poems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """장소에 어울리는 시 후보 목록(사용자가 직접 고를 수 있게).

    같은 권역 시 + 전국 공용 시를 권역 우선·중복 제거 순으로 돌려준다.
    후보가 없으면 전체 목록(자유 검색 등 권역 정보가 없을 때)."""
    region_key = _region_key_for_place(place)
    regional = [p for p in poems if region_key and region_key in p.get("region_keys", [])]
    universal = [p for p in poems if not p.get("region_keys")]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for p in regional + universal:
        pid = p.get("id", "")
        if pid not in seen:
            seen.add(pid)
            out.append(p)
    return out or list(poems)


def get_poem(poem_id: str | None, poems: list[dict[str, Any]]) -> dict[str, Any] | None:
    """id 로 시를 찾는다(사용자가 고른 시). 없으면 None."""
    if not poem_id:
        return None
    return next((p for p in poems if p.get("id") == poem_id), None)


def to_display(poem: dict[str, Any] | None) -> dict[str, Any] | None:
    """표시용 필드만 추린 dict(프론트 응답용). 입력이 None 이면 None."""
    if not poem:
        return None
    return {k: poem.get(k, "") for k in DISPLAY_FIELDS}
