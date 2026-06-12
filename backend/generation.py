"""
BGM 생성 보조 기능.

우선순위: ElevenLabs Music(API 키 있으면) → fal.ai stable-audio → None(호출부가 캐싱 음원으로 폴백).
생성된 음원은 data/audio/ 에 저장하고 /audio/<파일명> 경로(프론트가 프록시로 접근)를 반환한다.
같은 프롬프트는 파일 해시로 캐싱해 재호출(특히 무료 크레딧) 낭비를 막는다.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 생성된 음원 저장 위치 — main.py 가 /audio 로 마운트하는 디렉터리와 동일.
_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "audio")

# 생성 길이(초). ElevenLabs 는 ms 단위(10초~5분)를 받는다.
_LENGTH_SECONDS = 60
# fal.ai stable-audio 는 약 47초가 상한 — 폴백 경로는 이 값으로 잘라 보낸다.
_FAL_MAX_SECONDS = 47
# ElevenLabs 생성 대기 한도(초). 생성 시간은 길이에 비례해 늘어난다.
_ELEVENLABS_TIMEOUT = 180

# 사용자 프롬프트 최대 길이(비용·악용 방지). 초과분은 잘라낸다.
_MAX_USER_PROMPT = 200

# ── 한글 통제어휘 → 영어 매핑 ─────────────────────────────────
# ElevenLabs Music 은 영어를 훨씬 잘 이해하므로, 데이터의 한글 장르/악기/무드/
# 장소 키워드를 영어로 옮겨 프롬프트 품질을 높인다. 매핑에 없는 값은 버린다
# (설명에서 잘려 나온 무드 조각 등 노이즈를 프롬프트에 넣지 않기 위함).
_EN_GENRE: dict[str, str] = {
    "정악": "Korean court music (jeongak)",
    "민요": "Korean folk song (minyo)",
    "국악 BGM": "Korean traditional background music",
    "국악 샘플": "Korean traditional instrumental",
}
_EN_INSTRUMENT: dict[str, str] = {
    "가야금": "gayageum (Korean zither)",
    "거문고": "geomungo (bass zither)",
    "대금": "daegeum (bamboo flute)",
    "단소": "danso (small bamboo flute)",
    "피리": "piri (double-reed pipe)",
    "해금": "haegeum (two-string fiddle)",
    "아쟁": "ajaeng (bowed zither)",
    "태평소": "taepyeongso (Korean oboe)",
    "장구": "janggu (hourglass drum)",
    "소리": "pansori vocals",
    "국악 합주": "Korean traditional ensemble",
}
_EN_MOOD: dict[str, str] = {
    "고요함": "serene", "평온함": "peaceful", "평화로운": "peaceful",
    "차분한": "calm", "잔잔한": "tranquil", "장엄함": "majestic",
    "비장한": "solemn", "의례적": "ceremonial", "정제됨": "refined",
    "우아함": "elegant", "서정적": "lyrical", "애상적": "melancholic",
    "애절함": "plaintive", "그리운듯한": "nostalgic", "아련한": "wistful",
    "신나는": "lively", "흥겨움": "festive", "활기찬": "energetic",
    "경쾌함": "upbeat", "신성한": "sacred", "명상적": "meditative",
    "고독한": "lonely", "외로운": "lonely", "어두운": "dark",
    "섬뜩한": "eerie", "포근한": "cozy", "향토적": "rustic",
    "고전적인": "classical", "힘찬": "powerful", "비극적인": "tragic",
}
_EN_KEYWORD: dict[str, str] = {
    "궁중": "royal court", "궁중음악": "court music", "왕실": "royal",
    "의례": "ceremonial", "장엄": "majestic", "정제": "refined",
    "정악": "court music", "제례악": "ritual music", "유교": "Confucian",
    "선비": "scholarly", "전통": "traditional", "민속": "folk",
    "민요": "folk song", "농악": "farmers' percussion music",
    "사물놀이": "samulnori percussion", "판소리": "pansori",
    "산조": "sanjo", "탈놀이": "mask-dance", "흥겨움": "festive",
    "활기": "lively", "장터": "marketplace", "시장": "market",
    "공동체": "communal", "마을": "village", "한옥": "hanok house",
    "고즈넉": "tranquil", "향토": "rustic", "고장": "hometown",
    "한국": "Korean", "문화유산": "cultural heritage",
    "경기": "Gyeonggi region", "영남": "Yeongnam region", "호남": "Honam region",
}


def _map_terms(values: list[str], table: dict[str, str], limit: int) -> list[str]:
    """한글 통제어휘 리스트 → 영어(매핑된 것만), 순서 보존 중복 제거 후 limit개."""
    out: list[str] = []
    for v in values:
        en = table.get(v)
        if en and en not in out:
            out.append(en)
        if len(out) >= limit:
            break
    return out


# 고전 시 심상(imagery_en) 최대 길이 — 프롬프트가 한쪽으로 쏠리지 않게 제한.
_MAX_POEM_IMAGERY = 160

# ── 프롬프트 고정 앵커 (생성 길이에 따라 선택) ─────────────────────
# 짧은 클립(~30초)은 한 텍스처를 유지하면 충분하지만, 긴 생성은 모델이 구조
# (전개·전환·끝맺음)를 스스로 지어내며 표류·반복·어색한 마무리가 생기기 쉽다.
# 긴 생성에는 구조를 명시하되, 시연(심사)용으로 단조롭지 않게 대비가 뚜렷한
# 섹션 구성·과감한 전환을 주문한다 — 무계획한 표류가 아니라 '의도된' 변화.
_ANCHOR_SHORT = "traditional Korean (gugak), instrumental, ambient background"
_ANCHOR_LONG = (
    "traditional Korean (gugak), instrumental, "
    "one piece in distinct contrasting sections: a serene atmospheric opening, "
    "an abrupt shift into a livelier, more dramatic passage with bold tempo and dynamic changes, "
    "and a striking memorable finale, cohesive Korean instrumentation throughout"
)
_LONG_FORM_SECONDS = 45  # 이 길이부터 구조 지침 앵커 사용


def _anchor() -> str:
    """생성 길이에 맞는 고정 앵커 구절."""
    return _ANCHOR_LONG if _LENGTH_SECONDS >= _LONG_FORM_SECONDS else _ANCHOR_SHORT


def build_prompt(
    place: dict[str, Any],
    top_track: dict[str, Any],
    user_prompt: str | None = None,
    poem: dict[str, Any] | None = None,
) -> str:
    """장소·매칭곡 정보(+선택적 사용자 텍스트·고전 시 심상)를 합쳐 영어 음악 생성 프롬프트를 만든다.

    구성: [사용자 텍스트] + [고전 시 심상(영어)] + [장소 키워드(영어)]
          + [매칭곡 악기/장르/무드(영어)] + [국악·instrumental·ambient 고정 앵커].
    사용자 텍스트·시가 비어 있으면 장소·매칭곡만으로 구성된다.
    """
    parts: list[str] = []

    if user_prompt and user_prompt.strip():
        parts.append(user_prompt.strip()[:_MAX_USER_PROMPT])

    # 고전 시의 심상을 앞쪽에 둬 생성 분위기를 이끌게 한다(시에서 영감받은 BGM).
    if poem and poem.get("imagery_en", "").strip():
        parts.append("inspired by a classical Korean poem: " + poem["imagery_en"].strip()[:_MAX_POEM_IMAGERY])

    place_kw = _map_terms(place.get("cultural_keywords", []), _EN_KEYWORD, limit=4)
    if place_kw:
        parts.append(", ".join(place_kw))

    instruments = _map_terms(top_track.get("instruments", []), _EN_INSTRUMENT, limit=3)
    if instruments:
        parts.append("featuring " + ", ".join(instruments))

    genre = _EN_GENRE.get(top_track.get("genre", ""), "traditional Korean")
    parts.append(f"{genre} style")

    mood = _map_terms(top_track.get("mood", []), _EN_MOOD, limit=2)
    if mood:
        parts.append(", ".join(mood) + " mood")

    parts.append(_anchor())
    return ", ".join(parts)


# ── 권역(토리) → 영어 묘사 구절 (핵심 정체성 → 부가 색채 순) ─────────────
# 권역 BGM 프롬프트에서 장소 키워드 자리를 대신한다. 사용자 텍스트 가중에 따라
# 앞에서부터 n개만 쓰므로, 구절 순서가 곧 중요도 순서다.
_EN_REGION: dict[str, list[str]] = {
    "sudo_chung": [
        "bright and graceful Gyeonggi folk style (gyeongtori) of the Seoul and Chungcheong region",
        "clear, refined, lilting melody over a gutgeori rhythm",
        "polished and elegant, urban yet traditional",
        "cheerful, accessible song-like phrasing",
    ],
    "gangwon": [
        "plaintive menari-tori melody of the Gangwon highlands",
        "slow, sorrowful descending lines with a rustic mountain feel",
        "lonely, wistful yet enduring atmosphere",
        "deep valley stillness, like a sigh carried on the wind",
    ],
    "yeongnam": [
        "vigorous menari-tori folk style of the Yeongnam (Gyeongsang) region",
        "fast, spirited tempo with bold, strong accents",
        "hearty and festive communal energy",
        "powerful, exuberant work-song drive",
    ],
    "honam": [
        "deep yukjabaegi-tori of the Honam (Jeolla) region, home of pansori",
        "thick vibrato and dramatic bending notes (sigimsae)",
        "soulful han — sorrowful yet powerful and expressive",
        "rich, theatrical southern folk phrasing",
    ],
    "jeju": [
        "island folk style of Jeju with level, unornamented melodic lines",
        "distinctive rolling island rhythms of sea and wind",
        "rustic local color, simple and earthy",
        "breezy coastal calm with a hint of dialect charm",
    ],
}

# ── 권역 프롬프트 가중 ───────────────────────────────────────
# 사용자 텍스트 길이가 이 값(자)에 닿으면 가중 1.0 — 사용자 묘사가 프롬프트를
# 주도하고 권역 묘사는 최소 구절로 줄어든다. 비어 있으면 권역 정보가 전부를 이끈다.
_USER_WEIGHT_FULL_CHARS = 120
_REGION_PHRASES_MAX = 4   # 사용자 텍스트 없음(가중 0)일 때 넣는 권역 구절 수
_REGION_PHRASES_MIN = 1   # 사용자 텍스트가 충분히 길 때(가중 1) 남기는 권역 구절 수
# 이 가중 이상이면 사용자 텍스트를 프롬프트 맨 앞에 둔다(앞쪽일수록 생성 영향↑).
_USER_LEADS_THRESHOLD = 0.5


def _user_weight(user_text: str) -> float:
    """사용자 프롬프트 길이 → [0,1] 가중. 길수록 사용자 묘사가 프롬프트를 주도한다."""
    return min(1.0, len(user_text) / _USER_WEIGHT_FULL_CHARS) if user_text else 0.0


def build_region_prompt(
    profile: dict[str, Any],
    top_track: dict[str, Any],
    user_prompt: str | None = None,
    poem: dict[str, Any] | None = None,
) -> str:
    """권역(토리) 정보와 사용자 텍스트를 길이 기반 가중으로 섞은 생성 프롬프트.

    구성은 build_prompt 와 동일하되 장소 키워드 자리에 권역 묘사 구절이 들어간다.
    사용자 텍스트가 길수록(가중↑) 권역 구절 수를 줄이고 사용자 텍스트를 앞세우며,
    짧거나 없으면 권역 묘사가 앞에서 분위기를 이끈다. 시 심상 주입은 build_prompt 와 동일.
    """
    user_text = (user_prompt or "").strip()[:_MAX_USER_PROMPT]
    weight = _user_weight(user_text)

    span = _REGION_PHRASES_MAX - _REGION_PHRASES_MIN
    n_region = _REGION_PHRASES_MAX - round(weight * span)
    region_parts = _EN_REGION.get(profile.get("key", ""), [])[:n_region]

    poem_part: str | None = None
    if poem and poem.get("imagery_en", "").strip():
        poem_part = "inspired by a classical Korean poem: " + poem["imagery_en"].strip()[:_MAX_POEM_IMAGERY]

    parts: list[str] = []
    if weight >= _USER_LEADS_THRESHOLD:
        # 사용자 주도: 사용자 → 시 → 권역
        parts.append(user_text)
        if poem_part:
            parts.append(poem_part)
        parts.extend(region_parts)
    else:
        # 권역 주도: 권역 → 시 → 사용자
        parts.extend(region_parts)
        if poem_part:
            parts.append(poem_part)
        if user_text:
            parts.append(user_text)

    instruments = _map_terms(top_track.get("instruments", []), _EN_INSTRUMENT, limit=3)
    if instruments:
        parts.append("featuring " + ", ".join(instruments))

    genre = _EN_GENRE.get(top_track.get("genre", ""), "traditional Korean")
    parts.append(f"{genre} style")

    mood = _map_terms(top_track.get("mood", []), _EN_MOOD, limit=2)
    if mood:
        parts.append(", ".join(mood) + " mood")

    parts.append(_anchor())
    return ", ".join(parts)


def _cache_path(prompt: str, suffix: str, length_seconds: int) -> tuple[str, str]:
    """프롬프트+생성 길이 해시 기반 파일 경로(절대)와 공개 URL(/audio/...).

    길이를 키에 넣어, 생성 길이를 바꾸면 같은 프롬프트라도 새로 생성된다
    (예전 30초 캐시 파일이 더 긴 요청에 재사용되는 것을 방지)."""
    digest = hashlib.sha1(f"{suffix}:{length_seconds}:{prompt}".encode("utf-8")).hexdigest()[:16]
    filename = f"gen_{suffix}_{digest}.mp3"
    return os.path.join(_AUDIO_DIR, filename), f"/audio/{filename}"


async def _generate_elevenlabs(prompt: str, api_key: str) -> str | None:
    """ElevenLabs Music API. 성공 시 /audio/<파일명>, 실패 시 None.

    /v1/music 는 mp3 **바이트**를 그대로 반환하므로(호스팅 URL 아님) 파일로 저장한다.
    """
    abs_path, public_url = _cache_path(prompt, "el", _LENGTH_SECONDS)
    if os.path.exists(abs_path):
        logger.info("ElevenLabs 캐시 적중 — 재호출 생략: %s", public_url)
        return public_url

    import httpx  # noqa: PLC0415
    try:
        os.makedirs(_AUDIO_DIR, exist_ok=True)
        async with httpx.AsyncClient(timeout=_ELEVENLABS_TIMEOUT) as client:
            resp = await client.post(
                "https://api.elevenlabs.io/v1/music",
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "prompt": prompt,
                    "music_length_ms": _LENGTH_SECONDS * 1000,
                    "model_id": "music_v1",
                },
            )
            resp.raise_for_status()
            # 일부 오류는 200 이 아닌 JSON 으로 옴 — content-type 으로 오디오 여부 확인.
            ctype = resp.headers.get("content-type", "")
            if "audio" not in ctype:
                logger.warning("ElevenLabs 비오디오 응답(content-type=%s): %s", ctype, resp.text[:300])
                return None
            with open(abs_path, "wb") as f:
                f.write(resp.content)
        logger.info("ElevenLabs 생성 완료: %s", public_url)
        return public_url
    except Exception as exc:
        logger.warning("ElevenLabs 생성 실패: %s", exc)
        return None


async def _generate_fal(prompt: str, api_key: str) -> str | None:
    """fal.ai stable-audio. 성공 시 호스팅 URL, 실패 시 None."""
    import httpx  # noqa: PLC0415
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://fal.run/fal-ai/stable-audio",
                headers={"Authorization": f"Key {api_key}"},
                json={"prompt": prompt, "seconds_total": min(_LENGTH_SECONDS, _FAL_MAX_SECONDS)},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["audio_file"]["url"]
    except Exception as exc:
        logger.warning("fal.ai 생성 실패: %s", exc)
        return None


async def generate_bgm(
    place: dict[str, Any],
    top_track: dict[str, Any],
    user_prompt: str | None = None,
    poem: dict[str, Any] | None = None,
    region_profile: dict[str, Any] | None = None,
) -> str | None:
    """
    BGM을 생성하고 재생 가능한 URL을 반환한다.
    user_prompt(선택)·poem(선택)은 장소·매칭곡 정보와 합쳐져 프롬프트가 된다.
    region_profile 이 있으면(소리 지도 권역 생성) 장소 키워드 대신 권역 묘사를
    사용자 텍스트 길이 가중으로 섞는다(build_region_prompt).
    공급자 키가 모두 없거나 전부 실패하면 None (폴백은 호출부가 캐싱 음원으로 처리).
    """
    if region_profile:
        prompt = build_region_prompt(region_profile, top_track, user_prompt, poem)
    else:
        prompt = build_prompt(place, top_track, user_prompt, poem)

    el_key = os.getenv("ELEVENLABS_MUSIC_API_KEY", "")
    if el_key:
        url = await _generate_elevenlabs(prompt, el_key)
        if url:
            return url

    fal_key = os.getenv("FAL_API_KEY", "")
    if fal_key:
        url = await _generate_fal(prompt, fal_key)
        if url:
            return url

    logger.info("생성 공급자 없음/전부 실패 — 폴백으로 위임")
    return None
