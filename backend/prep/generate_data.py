"""
오프라인 데이터 가공 스크립트.

장소(PLACES_RAW)와 국악방송 전국8도민요 MR 음원(CSV)을 정의/파싱하고,
임베딩을 사전 계산해 dict 포맷 JSON으로 저장한다.

임베딩 백엔드는 embeddings.embed_corpus 가 결정한다:
  - HF_API_KEY 있으면 ko-sroberta 768차원
  - 없으면 키워드 매칭 폴백 (34차원)

새 장소 추가: PLACES_RAW 에 dict 하나 추가 후 재실행하면 자동 임베딩.
음원 파일 다운로드: 이 스크립트는 메타+임베딩만 만든다. 실제 wav는
prep/download_audio.py 가 tracks.json 의 audio_source_url 로부터 받는다.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys

# Windows에서 stdout 리다이렉트 시 기본 cp949 → 한글/특수문자 인코딩 에러 방지.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# embeddings 모듈을 import 하기 위해 backend 디렉터리를 경로에 추가
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

from embeddings import (  # noqa: E402
    EMBED_TEXT_RECIPE,
    embed_corpus,
    place_recipe,
    region_recipe,
    track_recipe,
)
from regions import (  # noqa: E402
    REGION_PROFILES,
    region_affinity_for_music_region,
    region_keywords_for_music_region,
)

load_dotenv()

_ROOT = os.path.join(_BACKEND_DIR, "..")
_DATA_DIR = os.path.join(_ROOT, "data")
_CSV_NAME = "재단법인국악방송_전국8도민요MR_20240301.csv"


# ─────────────────────────────────────────────
# 장소 데이터 (히어로 4곳). 새 장소는 여기에 dict 추가만 하면 된다.
# ─────────────────────────────────────────────
PLACES_RAW = [
    {
        "id": "gyeongbokgung",
        "name": "경복궁",
        "region": "서울특별시",
        "music_region": "경기",
        "type": "궁궐",
        "lat": 37.5796,
        "lng": 126.9770,
        "description": "조선 왕조의 정궁으로 왕실 의례와 궁중 문화의 중심지. 장엄하고 정제된 왕실 문화를 상징한다.",
        "cultural_keywords": ["왕실", "궁중", "의례", "정제", "장엄", "정악", "궁중음악"],
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/98/3487598_image2_1.jpg",
        "image_copyright": "Type1",
    },
    {
        "id": "hahoe",
        "name": "안동 하회마을",
        "region": "경상북도 안동시",
        "music_region": "영남",
        "type": "민속마을",
        "lat": 36.5390,
        "lng": 128.5189,
        "description": "유네스코 세계문화유산으로 지정된 조선시대 씨족마을. 하회별신굿탈놀이 등 민속 문화가 살아있다.",
        "cultural_keywords": ["민속", "마을", "공동체", "활기", "탈놀이", "농악", "영남"],
        "image_url": "https://tong.visitkorea.or.kr/cms/resource/17/3506417_image2_1.jpg",
        "image_copyright": "Type3",
    },
    {
        "id": "jeonju_hanok",
        "name": "전주 한옥마을",
        "region": "전라북도 전주시",
        "music_region": "호남",
        "type": "한옥마을",
        "lat": 35.8148,
        "lng": 127.1527,
        "description": "700여 채 한옥이 모인 국내 최대 한옥 군락지. 판소리·전통 음식·전통 공예가 살아숨쉬는 전통문화 중심지.",
        "cultural_keywords": ["전통", "민속", "판소리", "호남", "공동체", "민요", "문화유산"],
        "image_url": "http://tong.visitkorea.or.kr/cms/resource/35/3506735_image2_1.jpg",
        "image_copyright": "Type1",
    },
    {
        "id": "namdaemun",
        "name": "남대문시장",
        "region": "서울특별시 중구",
        "music_region": "경기",
        "type": "전통시장",
        "lat": 37.5581,
        "lng": 126.9768,
        "description": "조선시대부터 이어온 서울 최대 전통 재래시장. 상인들의 활기찬 에너지와 민중 문화가 공존하는 생동감 넘치는 공간.",
        "cultural_keywords": ["민속", "활기", "공동체", "시장", "경기", "민요", "농악"],
        "image_url": "http://tong.visitkorea.or.kr/cms/resource/65/3336365_image2_1.jpg",
        "image_copyright": "Type3",
    },
]


# ─────────────────────────────────────────────
# 국악방송 CSV → 트랙 매핑 규칙
# ─────────────────────────────────────────────
# 민요 권역명 → (영문 id 접두, 매칭용 music_region, 분위기 태그)
# music_region 은 rules.REGION_MAP 의 값과 일치시켜 _region_score 가 동작하게 한다.
REGION_RULE: dict[str, dict[str, object]] = {
    "경기도": {"en": "gyeonggi", "music_region": "경기", "mood": ["흥겨움", "경쾌함", "서정적"]},
    "남도":   {"en": "namdo",    "music_region": "호남", "mood": ["구성짐", "애절함", "서정적"]},
    "강원도": {"en": "gangwon",  "music_region": "강원", "mood": ["서정적", "애상적", "향토적"]},
    "서도":   {"en": "seodo",    "music_region": "서도", "mood": ["애절함", "구성짐", "서정적"]},
    "제주도": {"en": "jeju",     "music_region": "제주", "mood": ["서정적", "향토적", "애상적"]},
}

# 권역별 수집 상한. 권역을 명시하면 그 수만큼만, **비워두면(또는 권역 생략) 전체 사용.**
# 현재: 빈 dict → CSV 105곡 전부 사용 (경기42·남도30·서도27·제주4·강원2, 모두 REGION_RULE 존재).
# 같은 공공누리 제1유형·같은 download_audio 파이프라인이라 새 코드 없이 81곡 즉시 추가.
REGION_PICK: dict[str, int] = {}  # 전체 105곡 사용 (상한 없음)

# 연주자 필드에서 추출할 악기 토큰 (괄호 안 표기 기준).
_KNOWN_INSTRUMENTS = ["장구", "피리", "대금", "아쟁", "가야금", "해금", "거문고", "북", "징", "꽹과리"]

# 라이선스: 사용자 확인 — 국악방송 공공개방음원 = 공공누리 제1유형.
_LICENSE_TYPE = "공공누리 제1유형"


def _parse_instruments(performer_field: str) -> list[str]:
    """'연주 : 이경섭(장구), 이호진(피리)...' 에서 악기 토큰 추출 + 소리(성악) 포함."""
    found = [ins for ins in _KNOWN_INSTRUMENTS if ins in performer_field]
    if "소리" in performer_field:
        found.append("소리")
    # 등장 순서 유지하며 중복 제거
    seen: set[str] = set()
    ordered = []
    for ins in found:
        if ins not in seen:
            seen.add(ins)
            ordered.append(ins)
    return ordered or ["장구", "소리"]


def _row_get(row: dict[str, str], idx: int) -> str:
    return list(row.values())[idx].strip()


def load_csv_tracks() -> list[dict]:
    """CSV를 파싱하고 권역별로 REGION_PICK 만큼 선별해 트랙 레코드 리스트를 만든다."""
    csv_path = os.path.join(_ROOT, _CSV_NAME)
    if not os.path.exists(csv_path):
        csv_path = os.path.join(_DATA_DIR, "raw", _CSV_NAME)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV를 찾을 수 없습니다: {_CSV_NAME}")

    with io.open(csv_path, encoding="euc-kr") as f:
        rows = list(csv.DictReader(f))

    picked_count: dict[str, int] = {}
    tracks: list[dict] = []
    for row in rows:
        code = _row_get(row, 0)          # 음원코드, e.g. "경기도-01"
        title = _row_get(row, 1)         # 자료명
        performers = _row_get(row, 3)    # 저자_연주자
        year = _row_get(row, 4)          # 제작년도
        csv_genre = _row_get(row, 5)     # 장르 (예: 통속민요/토속민요) — 임베딩 키워드 보강
        keywords = _row_get(row, 6)      # 키워드
        audio_url = _row_get(row, 7)     # 홈페이지 주소(URL) = wav 직링크

        region_name = code.rsplit("-", 1)[0]
        rule = REGION_RULE.get(region_name)
        if rule is None:  # REGION_RULE 에 없는 권역만 제외
            continue
        cap = REGION_PICK.get(region_name)  # None 이면 무제한 (전체 사용)
        if cap is not None and picked_count.get(region_name, 0) >= cap:
            continue
        picked_count[region_name] = picked_count.get(region_name, 0) + 1

        num = code.rsplit("-", 1)[1] if "-" in code else str(picked_count[region_name])
        tid = f"{rule['en']}_{num}"
        instruments = _parse_instruments(performers)
        region_label = region_name.replace("도", "") if region_name.endswith("도") else region_name

        description = (
            f"국악방송이 제작한 전국8도민요 MR 음원. {region_name} 권역의 민요 «{title}». "
            f"키워드: {keywords}."
        )
        attribution = f"{title}(국악방송, {year}) — {_LICENSE_TYPE}(출처표시)"

        tracks.append({
            "id": tid,
            "title": title,
            "genre": "민요",
            "sub_genre": f"{region_label} 민요",
            "region": str(rule["music_region"]),
            "instruments": instruments,
            "mood": list(rule["mood"]),
            "description": description,
            "keywords": f"{csv_genre},{keywords}" if csv_genre else keywords,
            "audio_path": f"/audio/igbf_{tid}.mp3",  # 소스는 wav, download_audio 가 mp3 로 변환
            "audio_source_url": audio_url,
            "asset_kind": "full_track",
            "source": "국악방송",
            "source_url": "https://www.igbf.kr",
            "license_type": _LICENSE_TYPE,
            "license_note": "국악방송 공공개방음원 (전국8도민요 MR, data.go.kr/igbf.kr)",
            "is_derivative_allowed": True,
            "attribution_text": attribution,
        })

    return tracks


# ─────────────────────────────────────────────
# 공유마당 궁중음악·정악 큐레이션 (경복궁 등 궁궐 테마용)
# data/raw/gongu_sound.json 의 «국악연주곡_*» 시리즈에서 정악 레퍼토리를 고른다.
# 전부 다운로드 가능한 MP3 + CCL(BY).
# ─────────────────────────────────────────────
_GONGU_JSON = os.path.join(_DATA_DIR, "raw", "gongu_sound.json")

# 정악 합주/실내악 대표 악기 (세부 악기 메타가 없어 권역 표준 편성 사용).
_JEONGAK_ENSEMBLE = ["피리", "대금", "해금", "가야금", "거문고", "장구"]
_GAGOK_ENSEMBLE = ["가야금", "거문고", "대금", "해금", "피리", "장구"]

# (제목 매칭어, sub_genre, mood, 악기, 설명템플릿). region 은 전부 경기(정악 중심).
COURT_PICKS: list[dict] = [
    {"match": "여민락", "sub": "궁중음악", "mood": ["장엄함", "정제됨", "의례적"],
     "ins": _JEONGAK_ENSEMBLE,
     "desc": "조선 궁중 정악 «여민락». 백성과 함께 즐긴다는 뜻의 웅장하고 정제된 궁중 관현악."},
    {"match": "유초신지곡_상령산", "sub": "영산회상", "mood": ["고요함", "명상적", "정제됨"],
     "ins": _JEONGAK_ENSEMBLE,
     "desc": "정악 실내악 영산회상 중 상령산(유초신지곡). 느리고 명상적인 풍류 관현악."},
    {"match": "중광지곡_상령산", "sub": "영산회상", "mood": ["고요함", "우아함", "정제됨"],
     "ins": _JEONGAK_ENSEMBLE,
     "desc": "정악 실내악 영산회상 중 상령산(중광지곡). 거문고 중심의 정제된 풍류 합주."},
    {"match": "유초신지곡_중령산", "sub": "영산회상", "mood": ["고요함", "정제됨", "우아함"],
     "ins": _JEONGAK_ENSEMBLE,
     "desc": "정악 실내악 영산회상 중 중령산. 상령산에 이어지는 유려한 풍류 관현악."},
    {"match": "천년만세", "sub": "풍류", "mood": ["우아함", "정제됨", "흥겨움"],
     "ins": _JEONGAK_ENSEMBLE,
     "desc": "정악 실내악 천년만세. 계면가락도드리 등으로 이어지는 우아한 풍류 합주."},
    {"match": "우조 이수대엽", "sub": "가곡", "mood": ["우아함", "격식", "고요함"],
     "ins": _GAGOK_ENSEMBLE,
     "desc": "조선 선비의 정가 가곡, 우조 이수대엽 «버들은». 격조 높은 전통 성악."},
    {"match": "계면조 태평가", "sub": "가곡", "mood": ["정제됨", "격식", "평온함"],
     "ins": _GAGOK_ENSEMBLE,
     "desc": "정가 가곡 계면조 태평가 «이랴도». 남녀창이 어우러지는 격식 있는 전통 성악."},
    {"match": "만파정식지곡", "sub": "궁중음악", "mood": ["장엄함", "정제됨", "의례적"],
     "ins": _JEONGAK_ENSEMBLE,
     "desc": "궁중 정악 만파정식지곡. 장중하고 정제된 궁중 관현악.",
     "exclude": ["피아노", "ver"]},
]

# CCL 표기 → licensing.py 가 아는 라이선스 키로 정규화.
_CCL_NORMALIZE = {
    "CCL(BY)": "CC BY", "CCL(BY-SA)": "CC BY-SA", "CCL(BY-ND)": "CC BY-ND",
    "CCL(BY-NC)": "CC BY-NC", "CCL(BY-NC-SA)": "CC BY-NC-SA", "CCL(BY-NC-ND)": "CC BY-NC-ND",
}


def load_court_tracks() -> list[dict]:
    """공유마당 «국악연주곡_*» 에서 정악 레퍼토리를 큐레이션해 트랙 레코드를 만든다."""
    if not os.path.exists(_GONGU_JSON):
        print(f"[경고] {_GONGU_JSON} 없음 → 궁중음악 트랙 건너뜀")
        return []
    with open(_GONGU_JSON, encoding="utf-8") as f:
        pool = json.load(f)
    yeon = [x for x in pool if x.get("title", "").startswith("국악연주곡")]

    tracks: list[dict] = []
    for pick in COURT_PICKS:
        exclude = pick.get("exclude", ["피아노", "ver."])
        match_word = pick["match"]
        chosen = next(
            (x for x in yeon
             if match_word in x["title"] and not any(e in x["title"] for e in exclude)),
            None,
        )
        if chosen is None:
            print(f"[경고] 궁중음악 매칭 실패: {match_word}")
            continue
        sid = chosen["source_id"]
        title = chosen["title"].replace("국악연주곡_", "").strip()
        author = chosen.get("author") or "저작자 미상"
        license_type = _CCL_NORMALIZE.get(chosen.get("license_type", ""), "CC BY")
        tracks.append({
            "id": f"gongu_{sid}",
            "title": title,
            "genre": "정악",
            "sub_genre": pick["sub"],
            "region": "경기",  # 정악·궁중음악은 경기(서울) 중심
            "instruments": list(pick["ins"]),
            "mood": list(pick["mood"]),
            "description": pick["desc"],
            "keywords": f"정악,궁중음악,{pick['sub']}",
            "audio_path": f"/audio/gongu_{sid}.mp3",
            "audio_source_url": chosen["audio_url"],
            "asset_kind": "full_track",
            "source": "공유마당",
            "source_url": chosen.get("source_url", "https://gongu.copyright.or.kr"),
            "license_type": license_type,
            "license_note": "공유마당 공유저작물 (국악연주곡 시리즈)",
            "is_derivative_allowed": True,
            "attribution_text": f"«{title}» / {author} / {license_type} (출처: 공유마당)",
        })
    return tracks


# ─────────────────────────────────────────────
# 공유마당 추가 풀 (gongu_sound.json 5,423건) 자동 선별 — AGENTS.md §5.2, §5.5
#   라이선스 필터: creator_safe(=CC BY/CC0/공공누리1) + audio_url 보유 (사전계산 필드 사용).
#   관련성 필터: title 접두 시리즈로 한정해 효과음·비국악 잡음 배제 (정밀도 우선).
#   COURT_PICKS(수기 정악 8곡)와 source_id 로 중복 제거.
# 오디오는 '실제 노출하는 것만' 받는다는 선을 지키려 시리즈별 상한(cap)을 둔다(§2 시연 안정성).
# ─────────────────────────────────────────────
_BGM_DEFAULT_MOOD = ["국악", "전통"]
_JEONGAK_DEFAULT_MOOD = ["정제됨", "고요함", "우아함"]
# 변형/비완성본 배제 (피아노 편곡·노래방 MR 등).
_GONGU_VARIANT_EXCLUDE = ["피아노", "ver", "Ver", "VER", "노래방", "MR"]

# 시리즈 설정: (title 접두, genre, sub_genre, region, 상한, tags를 mood로 사용?, 기본 악기, 기본 mood)
GONGU_SERIES: list[dict] = [
    {"prefixes": ("국악 BGM", "국악 배경음"), "genre": "국악 BGM", "sub": "전통 배경음악",
     "region": "전국", "cap": 40, "mood_from_tags": True,
     "instruments": ["국악 합주"], "mood": _BGM_DEFAULT_MOOD},
    {"prefixes": ("국악연주곡",), "genre": "정악", "sub": "국악연주곡",
     "region": "경기", "cap": 30, "mood_from_tags": False,
     "instruments": _JEONGAK_ENSEMBLE, "mood": _JEONGAK_DEFAULT_MOOD},
]


# tags 는 공백 구분 서술 문자열("고독한 차분한 분위기 브금"). 의미 없는 필러를 제거하고
# 자연스러운 분위기 구절로 복원한다. 토큰을 콤마로 쪼개면 "여유가 넘치는" 같은 한 구절이
# "여유가", "넘치는" 두 조각으로 깨져 임베딩·태그 신호가 망가지므로, 표시·임베딩용으로는
# 필러만 걷어낸 공백 구절을 그대로 쓴다.
_GONGU_TAG_FILLER = {
    "분위기", "분위기의", "브금", "음악", "국악", "BGM", "배경음", "배경음악",
    "배경", "느낌", "느낌의", "곡", "사운드", "조성", "스타일",
}


def _gongu_tag_tokens(tags) -> list[str]:
    """tags(문자열 또는 리스트) → 토큰 리스트로 정규화."""
    if isinstance(tags, str):
        return tags.split()
    return [str(t) for t in (tags or [])]


def _gongu_mood_phrase(tags) -> str:
    """tags 에서 필러를 걷어낸 자연스러운 분위기 구절을 만든다 (임베딩·표시용).

    '여유가 넘치는 분위기 브금' → '여유가 넘치는'. 구절을 통째로 보존해
    임베딩 텍스트가 자연스러운 한국어가 되도록 한다(트랙별 변별 강화).
    """
    kept = [t.strip() for t in _gongu_tag_tokens(tags)
            if t.strip() and t.strip() not in _GONGU_TAG_FILLER]
    return " ".join(kept)


def _gongu_mood_from_tags(tags, fallback: list[str]) -> list[str]:
    """tags(분위기 서술어)에서 mood 토큰 리스트 추출(태그 매칭용). 필러 제외, 없으면 fallback."""
    out: list[str] = []
    for t in _gongu_tag_tokens(tags):
        t = t.strip()
        if t and t not in _GONGU_TAG_FILLER and t not in out:
            out.append(t)
        if len(out) >= 4:
            break
    return out or list(fallback)


def _gongu_instruments(text: str, fallback: list[str]) -> list[str]:
    """title/tags 텍스트에서 알려진 악기 토큰 추출. 없으면 fallback(시리즈 기본 편성)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for ins in _JEONGAK_ENSEMBLE + _KNOWN_INSTRUMENTS:
        if ins in text and ins not in seen:
            seen.add(ins)
            ordered.append(ins)
    return ordered or list(fallback)


def load_gongu_extra_tracks(exclude_ids: set[str]) -> list[dict]:
    """gongu_sound.json 에서 creator-safe 국악 BGM/연주곡을 시리즈별 상한으로 보강한다."""
    if not os.path.exists(_GONGU_JSON):
        return []
    with open(_GONGU_JSON, encoding="utf-8") as f:
        pool = json.load(f)

    seen: set[str] = set(exclude_ids)
    tracks: list[dict] = []
    for series in GONGU_SERIES:
        count = 0
        for x in pool:
            if count >= series["cap"]:
                break
            # 1) 라이선스 자동 필터 (§5.5): creator_safe + 재생 가능본만
            if not x.get("creator_safe") or not x.get("audio_url"):
                continue
            # 2) 관련성 필터: 시리즈 접두 + 변형본 제외
            title = (x.get("title") or "").strip()
            if not title.startswith(series["prefixes"]):
                continue
            if any(e in title for e in _GONGU_VARIANT_EXCLUDE):
                continue
            sid = str(x.get("source_id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            count += 1

            tags = x.get("tags") or ""
            mood = (_gongu_mood_from_tags(tags, series["mood"])
                    if series["mood_from_tags"] else list(series["mood"]))
            # 분위기 구절: BGM 은 tags 에서 복원한 자연 구절, 정악 시리즈는 정적 mood.
            mood_phrase = (_gongu_mood_phrase(tags) if series["mood_from_tags"]
                           else " ".join(mood)) or "전통적인"
            blob = f"{title} {' '.join(_gongu_tag_tokens(tags))}"
            instruments = _gongu_instruments(blob, series["instruments"])
            ins_text = ", ".join(instruments)
            license_type = _CCL_NORMALIZE.get(x.get("license_type", ""), "CC BY")
            author = x.get("author") or "저작자 미상"
            # 설명을 악기·분위기·세부장르로 다양화해 임베딩이 트랙별로 변별되게 한다
            # (동일 템플릿이면 768차원에서도 벡터가 한 점에 뭉쳐 어디서나 같이 추천됨).
            description = (
                f"공유마당 자유이용 {series['sub']} «{title}». "
                f"{ins_text} 편성으로 빚어낸 {mood_phrase} 정서의 {series['genre']}."
            )
            tracks.append({
                "id": f"gongu_{sid}",
                "title": title,
                "genre": series["genre"],
                "sub_genre": series["sub"],
                "region": series["region"],            # '전국'/'경기' — 권역 매칭은 약하게, 의미·분위기 위주
                "instruments": instruments,
                "mood": mood,
                "description": description,
                "keywords": f"국악,{series['genre']},{mood_phrase}," + ",".join(mood),
                "audio_path": f"/audio/gongu_{sid}.mp3",
                "audio_source_url": x.get("audio_url"),
                "asset_kind": "full_track",
                "source": "공유마당",
                "source_url": x.get("source_url", "https://gongu.copyright.or.kr"),
                "license_type": license_type,
                "license_note": "공유마당 공유저작물 (자동 선별)",
                "is_derivative_allowed": bool(x.get("derivative_ok", True)),
                "attribution_text": f"«{title}» / {author} / {license_type} (출처: 공유마당)",
            })
    return tracks


# ─────────────────────────────────────────────
# 공유마당 국악연주곡 중 '권역 정체성이 뚜렷한 민요' 큐레이션.
# 전국8도민요 CSV 에 없는 권역(영남 등)의 음원 공백을 실제 다운로드 가능한 음원으로 메운다.
# 모두 CCL(BY) MP3. (제목 정확 매칭 → genre=민요, region=해당 권역)
# 충청은 별도 음원이 아니라 경토리(=경기) 친연성으로 매칭하므로 여기 두지 않는다.
# ─────────────────────────────────────────────
# source_id 로 정확 지정(제목이 "2015 토요명품공연…" 처럼 길거나 변형본이 섞여 있어 정확매칭이 안전).
# title 은 화면 표기명으로 덮어쓴다. (공개 풀에 영남 국악이 극히 희소 — 확인된 것만 수기 큐레이션.)
REGIONAL_FOLK_PICKS: list[dict] = [
    {"sid": "13263048", "title": "밀양아리랑", "region": "영남", "sub": "영남 민요",
     "mood": ["씩씩함", "호쾌함", "흥겨움"],
     "instruments": ["피리", "대금", "해금", "가야금", "거문고", "장구"],
     "desc": "경상도 대표 민요 «밀양아리랑» 국악 연주. 미·솔·라·도·레 메나리토리의 "
             "억양이 강하고 호쾌하며 씩씩한 영남 가락."},
    # NOTE: 동래학춤(sid 12822838, 공공누리1)은 메타는 영남 적합이나 gongu wrtFileMediaPlay
    # 엔드포인트가 0바이트(재생 불가)를 반환 → 제외. 토요명품공연 음원은 직링크 미제공.
    # 공개 풀(공유마당 5,423 + 국악연주곡 943 + 국립국악원 악구 13,563)을 전수 조사한 결과
    # 재생 가능한 영남 전용 국악 음원은 밀양아리랑이 유일. 추가는 외부 음원 확보 필요.
]


def _normalize_license(raw: str) -> tuple[str, str]:
    """공유마당 라이선스 표기 → (정규화 license_type, license_note)."""
    if raw.startswith("공공누리"):
        return "공공누리 제1유형", "공유마당 공공저작물 (공공누리 제1유형, 영남 음원 큐레이션)"
    return _CCL_NORMALIZE.get(raw, "CC BY"), "공유마당 공유저작물 (영남 음원 큐레이션)"


def load_regional_folk_tracks(exclude_sids: set[str]) -> list[dict]:
    """공유마당에서 권역색이 뚜렷한 영남 음원을 source_id 로 정확 큐레이션한다(CSV 공백 보강)."""
    if not os.path.exists(_GONGU_JSON):
        return []
    with open(_GONGU_JSON, encoding="utf-8") as f:
        pool = json.load(f)
    by_sid = {str(x.get("source_id")): x for x in pool}
    seen = set(exclude_sids)
    tracks: list[dict] = []
    for pick in REGIONAL_FOLK_PICKS:
        sid = pick["sid"]
        x = by_sid.get(sid)
        if x is None or not x.get("audio_url") or not x.get("creator_safe") or sid in seen:
            print(f"[경고] 영남 음원 사용 불가/중복: {pick['title']} (sid {sid})")
            continue
        seen.add(sid)
        title = pick["title"]
        license_type, license_note = _normalize_license(x.get("license_type", ""))
        author = x.get("author") or "저작자 미상"
        tracks.append({
            "id": f"gongu_{sid}",
            "title": title,
            "genre": "민요",
            "sub_genre": pick["sub"],
            "region": pick["region"],          # 실제 권역 → region_score 1.0 (전용 음원)
            "instruments": list(pick["instruments"]),
            "mood": list(pick["mood"]),
            "description": pick["desc"],
            "keywords": f"민요,{pick['region']}," + ",".join(pick["mood"]),
            "audio_path": f"/audio/gongu_{sid}.mp3",
            "audio_source_url": x["audio_url"],
            "asset_kind": "full_track",
            "source": "공유마당",
            "source_url": x.get("source_url", "https://gongu.copyright.or.kr"),
            "license_type": license_type,
            "license_note": license_note,
            "is_derivative_allowed": bool(x.get("derivative_ok", True)),
            "attribution_text": f"«{title}» / {author} / {license_type} (출처: 공유마당)",
        })
    return tracks


def _write_payload(filename: str, list_key: str, records: list[dict],
                   model: str, dim: int) -> None:
    payload = {
        "embedding_model": model,
        "embedding_dim": dim,
        "embed_text_recipe": EMBED_TEXT_RECIPE,
        list_key: records,
    }
    with open(os.path.join(_DATA_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"{filename} 저장: {len(records)}건 ({model}, {dim}차원)")


def _load_tourapi_places() -> list[dict]:
    """collect_places.py 가 생성한 data/raw/tourapi_places.json 을 읽는다.
    파일이 없으면 빈 리스트 반환 (선택적 — AGENTS.md §5.1 Phase 3.5)."""
    path = os.path.join(_DATA_DIR, "raw", "tourapi_places.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # music_region 이 None 인 경우 DEFAULT_MUSIC_REGION 으로 채움
    from rules import DEFAULT_MUSIC_REGION, REGION_MAP
    for p in data:
        if not p.get("music_region"):
            # addr1 기반 재시도 후 기본값
            region_text = p.get("region", "")
            p["music_region"] = next(
                (v for k, v in REGION_MAP.items() if k in region_text),
                DEFAULT_MUSIC_REGION,
            )
    return data


def load_gugak_samples() -> list[dict]:
    """collect_gugak_samples.py 가 만든 data/raw/gugak_samples.json (sample_loop) 을 읽는다.
    파일 없으면 빈 리스트 (선택적 — AGENTS.md §5.2 ③)."""
    path = os.path.join(_DATA_DIR, "raw", "gugak_samples.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        samples = json.load(f)
    # 소스는 wav 이지만 download_audio 가 mp3 로 변환하므로 audio_path 를 .mp3 로 정규화.
    for s in samples:
        if s.get("audio_path", "").endswith(".wav"):
            s["audio_path"] = s["audio_path"][:-4] + ".mp3"
    return samples


def build_json() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)

    # 히어로 4곳 + TourAPI 수집 장소 병합 (중복 id 제거, 히어로 우선)
    tourapi_places = _load_tourapi_places()
    hero_ids = {p["id"] for p in PLACES_RAW}
    extra = [p for p in tourapi_places if p["id"] not in hero_ids]
    if extra:
        print(f"TourAPI 장소 {len(extra)}곳 추가 병합")
    places = [dict(p) for p in PLACES_RAW] + extra

    # 토리 친연성(region_affinity)을 각 장소에 저장한다. 일반 장소 매칭에서도 영남→강원
    # (메나리 형제)·충청→경기(경토리 형제) 음원을 region_score 1.0 으로 받게 하는 브리지.
    # 전용 음원이 없는 권역(영남·충청)이 구조적으로 전국 공용 음원에만 묻히는 문제를 푼다.
    for p in places:
        p["region_affinity"] = region_affinity_for_music_region(p.get("music_region", ""))

    # 트랙 풀: 정악(수기) + 전국8도민요(105) + 권역민요 보강(영남 등) + 공유마당 자동 보강 + 샘플
    court = load_court_tracks()
    folk = load_csv_tracks()
    court_sids = {t["id"][len("gongu_"):] for t in court}  # 공유마당 중복(source_id) 방지
    # 권역민요(영남 밀양아리랑 등)를 먼저 확보하고, 그 source_id 는 일반 보강(정악/BGM)에서 제외.
    regional = load_regional_folk_tracks(court_sids)
    regional_sids = {t["id"][len("gongu_"):] for t in regional}
    gongu_extra = load_gongu_extra_tracks(court_sids | regional_sids)
    samples = load_gugak_samples()  # 국립국악원 sample_loop (있으면)
    # id 중복 제거 (sample 이 기존 트랙과 겹치지 않도록)
    existing_ids = {t["id"] for t in court + folk + regional + gongu_extra}
    samples = [s for s in samples if s["id"] not in existing_ids]
    tracks = court + folk + regional + gongu_extra + samples
    print(f"트랙 구성: 정악(수기) {len(court)} + 민요 {len(folk)} + 권역민요 보강 {len(regional)} "
          f"+ 공유마당 보강 {len(gongu_extra)} + 국립국악원 샘플 {len(samples)} = {len(tracks)}곡")

    # 권역 프로필(regions.py) — 지도 색상 + 권역 클릭 추천의 의미 기준.
    regions = [dict(r) for r in REGION_PROFILES]

    # 한 번에 임베딩해 places·tracks·regions 가 동일 모드/차원을 쓰도록 보장한다.
    # place 임베딩은 소속 권역의 음악 특징 키워드로 강화한다(저장 필드는 불변, 입력만 강화).
    place_texts = [
        place_recipe(p) + " " + " ".join(region_keywords_for_music_region(p.get("music_region", "")))
        for p in places
    ]
    track_texts = [track_recipe(t) for t in tracks]
    region_texts = [region_recipe(r) for r in regions]
    all_vecs, model, dim = embed_corpus(place_texts + track_texts + region_texts)

    n_p, n_t = len(places), len(tracks)
    for p, vec in zip(places, all_vecs[:n_p]):
        p["embedding"] = vec
    for t, vec in zip(tracks, all_vecs[n_p:n_p + n_t]):
        t["embedding"] = vec
    for r, vec in zip(regions, all_vecs[n_p + n_t:]):
        r["embedding"] = vec

    _write_payload("places.json", "places", places, model, dim)
    _write_payload("tracks.json", "tracks", tracks, model, dim)
    _write_payload("regions.json", "regions", regions, model, dim)


if __name__ == "__main__":
    build_json()
