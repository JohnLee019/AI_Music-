"""
BGM 생성 보조 기능 (fal.ai / ElevenLabs Music).
외부 API 실패 시 캐싱된 폴백 음원을 반환한다.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 생성 프롬프트 템플릿 — traditional Korean / gugak / instrumental 앵커 고정
_PROMPT_TEMPLATE = (
    "{genre} music featuring {instruments}, {mood} atmosphere, "
    "traditional Korean (gugak), instrumental, ambient background"
)

# 폴백 캐싱 음원 (미리 생성해 둔 예시)
_FALLBACK: dict[str, str] = {
    "gyeongbokgung": "/audio/gen_gyeongbokgung_fallback.mp3",
    "hahoe": "/audio/gen_hahoe_fallback.mp3",
    "jeonju_hanok": "/audio/gen_jeonju_fallback.mp3",
    "namdaemun": "/audio/gen_namdaemun_fallback.mp3",
}


def build_prompt(place: dict[str, Any], top_track: dict[str, Any]) -> str:
    genre = top_track.get("genre", "traditional Korean")
    instruments = ", ".join(top_track.get("instruments", ["gayageum"])[:3])
    mood = ", ".join(top_track.get("mood", ["calm"])[:2])
    return _PROMPT_TEMPLATE.format(genre=genre, instruments=instruments, mood=mood)


async def generate_bgm(place: dict[str, Any], top_track: dict[str, Any]) -> str:
    """
    BGM을 생성하고 audio_url을 반환한다.
    FAL_API_KEY 미설정 또는 오류 시 폴백 URL을 반환한다.
    """
    fal_key = os.getenv("FAL_API_KEY", "")
    if not fal_key:
        logger.info("FAL_API_KEY 미설정 — 폴백 반환")
        return _get_fallback(place["id"])

    prompt = build_prompt(place, top_track)
    try:
        import httpx  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://fal.run/fal-ai/stable-audio",
                headers={"Authorization": f"Key {fal_key}"},
                json={"prompt": prompt, "seconds_total": 30},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["audio_file"]["url"]
    except Exception as exc:
        logger.warning("BGM 생성 실패, 폴백 반환: %s", exc)
        return _get_fallback(place["id"])


def _get_fallback(place_id: str) -> str:
    return _FALLBACK.get(place_id, "/audio/gen_default_fallback.mp3")
