"""
오프라인 데이터 가공 스크립트.
장소·트랙 메타데이터를 정의하고, TF-IDF 기반 임베딩을 사전 계산해 JSON으로 저장한다.
실 서비스용으로는 sentence-transformers 모델로 교체 권장.
"""
import json
import math
import os

# 32차원 문화 키워드 공간 (차원 인덱스 고정)
KEYWORD_DIMS = [
    "왕실", "궁중", "의례", "장엄함", "정제됨",          # 0-4 궁궐
    "민속", "마을", "농촌", "공동체", "활기",             # 5-9 민속
    "전통", "역사", "문화유산", "격식", "고요함",         # 10-14 공통
    "정악", "궁중음악", "관현악",                         # 15-17 정악
    "민요", "농악", "사물놀이", "풍물",                   # 18-21 민속악
    "판소리", "산조", "가곡", "독주",                     # 22-25 성악/독주
    "경기", "영남", "호남", "충청",                       # 26-29 권역
    "대금", "가야금", "장구", "피리",                     # 30-33 악기
]

def make_embedding(scores: dict[str, float]) -> list[float]:
    """키워드 점수 딕셔너리 → L2 정규화 벡터."""
    vec = [scores.get(k, 0.0) for k in KEYWORD_DIMS]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


# ─────────────────────────────────────────────
# 장소 데이터
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
        "cultural_keywords": ["왕실", "궁중", "의례", "정제됨", "장엄함", "정악", "궁중음악"],
        "embedding_scores": {
            "왕실": 1.0, "궁중": 1.0, "의례": 0.9, "장엄함": 0.9, "정제됨": 0.8,
            "전통": 0.7, "역사": 0.8, "문화유산": 0.7, "격식": 0.8, "고요함": 0.5,
            "정악": 0.8, "궁중음악": 1.0, "관현악": 0.6, "경기": 0.9,
        },
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
        "embedding_scores": {
            "민속": 1.0, "마을": 1.0, "공동체": 0.9, "활기": 0.8, "농촌": 0.7,
            "전통": 0.8, "역사": 0.7, "문화유산": 0.9, "농악": 0.9, "풍물": 0.8,
            "사물놀이": 0.6, "영남": 1.0, "장구": 0.6,
        },
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
        "cultural_keywords": ["전통", "민속", "판소리", "호남", "공동체", "한옥", "문화유산"],
        "embedding_scores": {
            "민속": 0.8, "마을": 0.9, "공동체": 0.7, "활기": 0.7,
            "전통": 1.0, "역사": 0.7, "문화유산": 0.8, "고요함": 0.5,
            "판소리": 1.0, "산조": 0.7, "가곡": 0.6, "민요": 0.7,
            "호남": 1.0, "가야금": 0.6,
        },
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
        "cultural_keywords": ["민속", "활기", "공동체", "시장", "경기", "사물놀이", "민요"],
        "embedding_scores": {
            "민속": 0.9, "공동체": 0.8, "활기": 1.0, "농촌": 0.3,
            "전통": 0.7, "역사": 0.6,
            "민요": 0.8, "농악": 0.6, "사물놀이": 1.0, "풍물": 0.9,
            "경기": 1.0, "장구": 0.8,
        },
    },
]

# ─────────────────────────────────────────────
# 트랙 데이터 (국립국악원·공유마당 자유이용 음원 기반)
# ─────────────────────────────────────────────
TRACKS_RAW = [
    # ── 정악 / 궁중음악 ──────────────────────────
    {
        "id": "sujecheon",
        "title": "수제천",
        "genre": "정악",
        "sub_genre": "궁중음악",
        "region": "경기",
        "instruments": ["피리", "대금", "해금", "장구", "편종"],
        "mood": ["장엄함", "정제됨", "의례적", "고요함"],
        "description": "조선 궁중 연례악 중 하나로 왕실 의례에 사용된 대표적 정악. 느리고 장중한 흐름이 특징.",
        "audio_path": "/audio/sujecheon.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "왕실": 0.9, "궁중": 1.0, "의례": 1.0, "장엄함": 1.0, "정제됨": 0.9,
            "격식": 0.9, "고요함": 0.7,
            "정악": 1.0, "궁중음악": 1.0, "관현악": 0.7,
            "경기": 0.8, "피리": 1.0, "대금": 0.8,
        },
    },
    {
        "id": "yeomillak",
        "title": "여민락",
        "genre": "정악",
        "sub_genre": "궁중음악",
        "region": "경기",
        "instruments": ["피리", "대금", "해금", "거문고", "가야금", "장구", "북"],
        "mood": ["장엄함", "고귀함", "의례적"],
        "description": "세종대왕이 창제한 궁중음악으로 '백성과 함께 즐긴다'는 뜻. 웅장하면서도 유려한 선율.",
        "audio_path": "/audio/yeomillak.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "왕실": 1.0, "궁중": 1.0, "의례": 0.9, "장엄함": 1.0, "정제됨": 0.8,
            "역사": 0.8, "격식": 0.8,
            "정악": 1.0, "궁중음악": 1.0, "관현악": 0.9,
            "경기": 0.8, "가야금": 0.7, "대금": 0.7,
        },
    },
    {
        "id": "jongmyo_jeryeak",
        "title": "종묘제례악",
        "genre": "정악",
        "sub_genre": "제례음악",
        "region": "경기",
        "instruments": ["편경", "편종", "피리", "대금", "해금", "아쟁", "징", "북"],
        "mood": ["장엄함", "의례적", "경건함", "엄숙함"],
        "description": "유네스코 인류무형문화유산. 조선 왕실 종묘 제사에 쓰이는 음악으로 경건하고 웅장하다.",
        "audio_path": "/audio/jongmyo.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "왕실": 1.0, "궁중": 1.0, "의례": 1.0, "장엄함": 1.0, "정제됨": 1.0,
            "역사": 0.9, "격식": 1.0, "고요함": 0.3,
            "정악": 1.0, "궁중음악": 0.9, "관현악": 0.8,
            "경기": 0.8, "피리": 0.8,
        },
    },
    # ── 영남 민속악 ──────────────────────────────
    {
        "id": "hahoe_byeolsingut",
        "title": "하회별신굿 무가",
        "genre": "민속악",
        "sub_genre": "무속음악",
        "region": "영남",
        "instruments": ["장구", "징", "꽹과리", "북"],
        "mood": ["활기", "신명남", "공동체적", "역동적"],
        "description": "안동 하회마을 전승 하회별신굿탈놀이의 굿 음악. 마을 공동체의 신명과 축제 분위기.",
        "audio_path": "/audio/hahoe_byeolsingut.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 1.0, "마을": 0.9, "공동체": 1.0, "활기": 1.0, "농촌": 0.7,
            "전통": 0.8, "문화유산": 0.9,
            "농악": 0.8, "사물놀이": 0.8, "풍물": 0.7,
            "영남": 1.0, "장구": 1.0,
        },
    },
    {
        "id": "gyeonggi_minyo",
        "title": "경기 민요 모음",
        "genre": "민속악",
        "sub_genre": "민요",
        "region": "경기",
        "instruments": ["장구", "소리(독창)", "해금"],
        "mood": ["활기", "서정적", "흥겨움"],
        "description": "경기 지역 민요 모음. 아리랑·도라지타령·노랫가락 등 친근하고 흥겨운 선율.",
        "audio_path": "/audio/gyeonggi_minyo.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 0.9, "마을": 0.7, "공동체": 0.8, "활기": 0.9,
            "전통": 0.7,
            "민요": 1.0,
            "경기": 1.0, "장구": 0.7,
        },
    },
    {
        "id": "yeongnam_minyo",
        "title": "경상도 민요 모음",
        "genre": "민속악",
        "sub_genre": "민요",
        "region": "영남",
        "instruments": ["장구", "소리", "피리"],
        "mood": ["흥겨움", "서정적", "구성짐"],
        "description": "경상도 지역 민요 모음. 밀양아리랑·쾌지나칭칭나네 등 경상도 특유의 구성진 민요.",
        "audio_path": "/audio/yeongnam_minyo.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 1.0, "마을": 0.8, "공동체": 0.8, "활기": 0.8,
            "전통": 0.7,
            "민요": 1.0,
            "영남": 1.0, "장구": 0.7, "피리": 0.5,
        },
    },
    # ── 호남 민속악 ──────────────────────────────
    {
        "id": "pansori_chunhyang",
        "title": "춘향가 (판소리)",
        "genre": "민속악",
        "sub_genre": "판소리",
        "region": "호남",
        "instruments": ["소리(독창)", "고수(장구)"],
        "mood": ["서정적", "구성짐", "애절함", "활기"],
        "description": "대표적 판소리 다섯 마당 중 하나. 이도령과 춘향의 사랑 이야기를 소리꾼이 극적으로 풀어낸다.",
        "audio_path": "/audio/pansori_chunhyang.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 0.8, "공동체": 0.6, "활기": 0.7,
            "전통": 0.9, "역사": 0.7, "문화유산": 0.8,
            "판소리": 1.0, "독주": 0.7,
            "호남": 1.0,
        },
    },
    {
        "id": "gayageum_sanjo",
        "title": "가야금 산조",
        "genre": "민속악",
        "sub_genre": "산조",
        "region": "호남",
        "instruments": ["가야금"],
        "mood": ["서정적", "고요함", "명상적", "구성짐"],
        "description": "가야금 단독 연주로 이루어지는 산조. 느린 진양조에서 빠른 휘모리까지 다양한 장단으로 구성.",
        "audio_path": "/audio/gayageum_sanjo.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 0.7, "활기": 0.5, "고요함": 0.8,
            "전통": 0.9,
            "산조": 1.0, "독주": 1.0,
            "호남": 0.9, "가야금": 1.0,
        },
    },
    {
        "id": "honam_nongak",
        "title": "호남 농악",
        "genre": "민속악",
        "sub_genre": "농악",
        "region": "호남",
        "instruments": ["꽹과리", "징", "장구", "북", "소고"],
        "mood": ["활기", "신명남", "공동체적", "역동적"],
        "description": "호남 지역 농악. 마당놀이·판굿 등 역동적 퍼포먼스와 함께하는 신명나는 음악.",
        "audio_path": "/audio/honam_nongak.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 1.0, "마을": 0.9, "공동체": 1.0, "활기": 1.0, "농촌": 0.9,
            "농악": 1.0, "사물놀이": 0.8, "풍물": 1.0,
            "호남": 1.0, "장구": 0.9,
        },
    },
    # ── 사물놀이 / 시장 ───────────────────────────
    {
        "id": "samulnori",
        "title": "사물놀이",
        "genre": "민속악",
        "sub_genre": "사물놀이",
        "region": "경기",
        "instruments": ["꽹과리", "징", "장구", "북"],
        "mood": ["활기", "역동적", "신명남", "흥겨움"],
        "description": "꽹과리·징·장구·북 4가지 타악기로 연주하는 실내 공연 음악. 농악의 실내 버전으로 박진감 넘침.",
        "audio_path": "/audio/samulnori.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 1.0, "공동체": 0.9, "활기": 1.0,
            "전통": 0.7,
            "민요": 0.3, "농악": 0.8, "사물놀이": 1.0, "풍물": 0.8,
            "경기": 0.9, "장구": 1.0,
        },
    },
    {
        "id": "pungmul",
        "title": "풍물굿",
        "genre": "민속악",
        "sub_genre": "농악",
        "region": "경기",
        "instruments": ["꽹과리", "징", "장구", "북", "태평소"],
        "mood": ["활기", "축제적", "신명남", "역동적"],
        "description": "농사·명절·마을 행사에 쓰이는 전통 풍물 음악. 신명나는 리듬과 마을 공동체 에너지.",
        "audio_path": "/audio/pungmul.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "민속": 1.0, "마을": 1.0, "공동체": 1.0, "활기": 1.0, "농촌": 0.9,
            "농악": 1.0, "사물놀이": 0.7, "풍물": 1.0,
            "경기": 0.8, "장구": 0.9,
        },
    },
    # ── 가곡 / 독주 ──────────────────────────────
    {
        "id": "gagok",
        "title": "가곡 (남창 우조)",
        "genre": "정악",
        "sub_genre": "가곡",
        "region": "경기",
        "instruments": ["가야금", "거문고", "대금", "해금", "피리", "장구"],
        "mood": ["정제됨", "격식", "고요함", "우아함"],
        "description": "조선 선비들이 즐기던 성악 장르. 정간보 악보로 전승되는 가장 격조 높은 전통 성악.",
        "audio_path": "/audio/gagok.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "왕실": 0.5, "정제됨": 0.9, "격식": 1.0, "고요함": 0.9,
            "전통": 0.9, "역사": 0.8,
            "정악": 0.9, "가곡": 1.0, "독주": 0.5,
            "경기": 0.9, "가야금": 0.7, "대금": 0.7,
        },
    },
    {
        "id": "daegeum_sanjo",
        "title": "대금 산조",
        "genre": "민속악",
        "sub_genre": "산조",
        "region": "경기",
        "instruments": ["대금"],
        "mood": ["서정적", "명상적", "고요함", "청아함"],
        "description": "대금 단독 연주 산조. 맑고 청아한 대금 음색으로 한국적 서정을 표현하는 독주 장르.",
        "audio_path": "/audio/daegeum_sanjo.mp3",
        "source": "국립국악원",
        "source_url": "https://www.gugak.go.kr",
        "license_type": "CC BY",
        "license_note": "국립국악원 디지털음원 공개 자료",
        "is_derivative_allowed": True,
        "embedding_scores": {
            "전통": 0.8, "고요함": 1.0,
            "산조": 1.0, "독주": 1.0,
            "경기": 0.7, "대금": 1.0,
        },
    },
]


def build_json():
    root = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    os.makedirs(root, exist_ok=True)

    # ── places.json ────────────────────────────
    places = []
    for p in PLACES_RAW:
        rec = {k: v for k, v in p.items() if k != "embedding_scores"}
        rec["embedding"] = make_embedding(p["embedding_scores"])
        places.append(rec)

    with open(os.path.join(root, "places.json"), "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)
    print(f"places.json 저장: {len(places)}건")

    # ── tracks.json ────────────────────────────
    tracks = []
    for t in TRACKS_RAW:
        rec = {k: v for k, v in t.items() if k != "embedding_scores"}
        rec["embedding"] = make_embedding(t["embedding_scores"])
        tracks.append(rec)

    with open(os.path.join(root, "tracks.json"), "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"tracks.json 저장: {len(tracks)}건")


if __name__ == "__main__":
    build_json()
