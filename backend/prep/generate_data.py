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

# embeddings 모듈을 import 하기 위해 backend 디렉터리를 경로에 추가
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

from embeddings import (  # noqa: E402
    EMBED_TEXT_RECIPE,
    embed_corpus,
    place_recipe,
    track_recipe,
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

# 권역별 선별 곡 수 (히어로 장소 커버리지 우선: 경기·남도 가중). 총합 ≈ 24.
REGION_PICK: dict[str, int] = {
    "경기도": 8,
    "남도": 8,
    "강원도": 2,
    "제주도": 4,
    "서도": 2,
}

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

    picked_count: dict[str, int] = {r: 0 for r in REGION_PICK}
    tracks: list[dict] = []
    for row in rows:
        code = _row_get(row, 0)          # 음원코드, e.g. "경기도-01"
        title = _row_get(row, 1)         # 자료명
        performers = _row_get(row, 3)    # 저자_연주자
        year = _row_get(row, 4)          # 제작년도
        keywords = _row_get(row, 6)      # 키워드
        audio_url = _row_get(row, 7)     # 홈페이지 주소(URL) = wav 직링크

        region_name = code.rsplit("-", 1)[0]
        rule = REGION_RULE.get(region_name)
        if rule is None or region_name not in REGION_PICK:
            continue
        if picked_count[region_name] >= REGION_PICK[region_name]:
            continue
        picked_count[region_name] += 1

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
            "keywords": keywords,
            "audio_path": f"/audio/igbf_{tid}.wav",
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


def build_json() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)

    places = [dict(p) for p in PLACES_RAW]
    tracks = load_court_tracks() + load_csv_tracks()  # 정악(궁중) + 전국8도민요

    # 한 번에 임베딩해 places·tracks 가 동일 모드/차원을 쓰도록 보장한다.
    place_texts = [place_recipe(p) for p in places]
    track_texts = [track_recipe(t) for t in tracks]
    all_vecs, model, dim = embed_corpus(place_texts + track_texts)

    for p, vec in zip(places, all_vecs[:len(places)]):
        p["embedding"] = vec
    for t, vec in zip(tracks, all_vecs[len(places):]):
        t["embedding"] = vec

    _write_payload("places.json", "places", places, model, dim)
    _write_payload("tracks.json", "tracks", tracks, model, dim)


if __name__ == "__main__":
    build_json()
