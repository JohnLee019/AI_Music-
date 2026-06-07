"""
음악 권역(토리) 프로필 테이블.

전국 소리 지도의 색상 권역 + 권역 클릭 추천의 근거가 되는 데이터.
웹 리서치(한국민족문화대백과사전·국립국악원 국악사전 등)로 정리한 각 권역의
음계·장단·시김새·정서·대표곡을 임베딩 텍스트로 풍부하게 담는다.

AGENTS.md §9: 매핑·규칙표는 매칭 로직과 분리해 별도 모듈로 둔다.

데이터 제약: 공개 음원 풀에 영남·충청 전용 트랙이 없다(경기 80·전국 80·호남 30·
서도 27·제주 4·강원 2). 그래서 권역 클릭 추천은 강화된 의미 프로필(임베딩) +
토리 친연성(region_affinity)으로 보강한다:
  - 수도권·충청(경토리) → 경기 음원
  - 영남(메나리토리) → 강원 음원(같은 동부민요 메나리토리 형제)
정확한 영남 민요 음원을 확보하면 region_affinity 에 "영남" 만 더하면 된다.
"""
from __future__ import annotations

from typing import Any

# ── 권역 프로필 (5대 색상 권역) ─────────────────────────
# key            : 안정적 식별자 (API·프론트 공용)
# label          : 화면 표기명
# tori           : 대표 토리(음악적 정서 분류)
# color          : 지도 폴리곤·범례 색 (한지톤)
# members        : 이 권역에 묶이는 place.music_region 값들 (지도 귀속·임베딩 강화용)
# track_region   : 권역 클릭 시 region_score 1.0 을 줄 대표 track.region
# region_affinity: track_region 동치로 볼 region 집합 (토리 형제 음원까지 포함)
# keywords       : 임베딩·태그 매칭용 음악 특징 토큰
# description    : 임베딩 본문 (음계·장단·시김새·정서·대표곡)
REGION_PROFILES: list[dict[str, Any]] = [
    {
        "key": "sudo_chung",
        "label": "수도권·충청",
        "tori": "경토리",
        "color": "#5B8DB8",
        "members": ["경기", "충청"],
        "track_region": "경기",
        "region_affinity": ["경기"],
        "keywords": [
            "경토리", "경기민요", "솔라도레미", "굿거리", "세마치", "도드리",
            "맑음", "경쾌함", "세련됨", "서정적", "대중적", "도시적",
        ],
        "description": (
            "수도권과 충청을 아우르는 경기 민요(경토리) 권역. "
            "솔·라·도·레·미 5음 음계에 굿거리·세마치·도드리 장단을 즐겨 쓴다. "
            "음색이 맑고 부드러우며 경쾌하고 세련된 가락으로, 도시적이고 대중적인 "
            "정서를 띤다. 대표곡으로 경복궁타령·창부타령·아리랑·노들강변 등이 있다."
        ),
        "songs": ["경복궁타령", "창부타령", "아리랑", "노들강변"],
    },
    {
        "key": "gangwon",
        "label": "강원",
        "tori": "메나리토리(애조)",
        "color": "#4E7C59",
        "members": ["강원"],
        "track_region": "강원",
        "region_affinity": ["강원"],
        "keywords": [
            "메나리토리", "강원민요", "미솔라도레", "엮음", "산간",
            "탄식", "애조", "구성짐", "꿋꿋함", "향토적", "느림",
        ],
        "description": (
            "강원 권역의 메나리토리. 미·솔·라·도·레 5음을 기본으로 최저음으로 "
            "하행해 종지하며, 라에서 미로 내려갈 때 솔을 거친다. 가락이 느리고 "
            "구성져 첩첩 산간의 고달프고 쓸쓸한 정서를 담아, 탄식하듯 애달프면서도 "
            "꿋꿋하다. 대표곡으로 정선아리랑·한오백년·강원도아리랑이 있다."
        ),
        "songs": ["정선아리랑", "한오백년", "강원도아리랑"],
    },
    {
        "key": "yeongnam",
        "label": "영남",
        "tori": "메나리토리(씩씩)",
        "color": "#C9882E",
        "members": ["영남"],
        "track_region": "강원",  # 영남 전용 음원 부재 → 메나리토리 형제(강원)로 브리지
        "region_affinity": ["강원", "영남"],
        "keywords": [
            "메나리토리", "경상도민요", "미솔라도레", "퇴성",
            "씩씩함", "호쾌함", "빠른템포", "활기참", "억양강함", "흥겨움",
        ],
        "description": (
            "영남(경상) 권역의 메나리토리. 강원과 같은 미·솔·라·도·레 음계를 쓰지만 "
            "경쾌하고 빠른 곡조가 많고 억양이 강해 호쾌하고 씩씩하며 활기차다. "
            "토속민요·무가·기악에까지 두루 나타날 만큼 영향력이 넓다. 대표곡으로 "
            "쾌지나칭칭나네·옹헤야·밀양아리랑이 있다."
        ),
        "songs": ["쾌지나칭칭나네", "옹헤야", "밀양아리랑"],
    },
    {
        "key": "honam",
        "label": "호남",
        "tori": "육자배기토리",
        "color": "#B5485B",
        "members": ["호남"],
        "track_region": "호남",
        "region_affinity": ["호남"],
        "keywords": [
            "육자배기토리", "남도민요", "판소리", "미라시도레", "시김새",
            "꺾는목", "요성", "한", "애절함", "극적", "깊음", "구성짐",
        ],
        "description": (
            "호남(전라) 권역의 육자배기토리. 미는 굵게 떨고 라는 평으로 내며 "
            "도는 시로 짧게 꺾어 흘러내리는 짙은 시김새가 특징이다. 깊은 한과 "
            "극적인 꺾는 음으로 애절하고 구성지다. 판소리의 본고장으로, 대표곡에 "
            "육자배기·진도아리랑·강강술래·남도흥타령이 있다."
        ),
        "songs": ["육자배기", "진도아리랑", "강강술래", "남도흥타령"],
    },
    {
        "key": "jeju",
        "label": "제주",
        "tori": "제주토리",
        "color": "#7E6BA8",
        "members": ["제주"],
        "track_region": "제주",
        "region_affinity": ["제주"],
        "keywords": [
            "제주민요", "라도레미", "레선법", "오돌또기", "이어도사나",
            "향토색", "방언", "독특함", "섬", "고만고만함",
        ],
        "description": (
            "제주 권역의 제주 민요. 라·도·레·미 계면조 계열과 레선법(오돌또기)을 "
            "쓰며, 육지와 달리 미를 떨지 않고 요성·꺾는목이 거의 없어 음계가 "
            "고만고만하다. 섬 특유의 향토색과 방언이 짙은 독특한 리듬을 지닌다. "
            "대표곡으로 오돌또기·이어도사나·너영나영이 있다."
        ),
        "songs": ["오돌또기", "이어도사나", "너영나영"],
    },
]


# ── place.music_region → 권역 key (지도 귀속 + 임베딩 강화용) ──
PLACE_REGION_GROUP: dict[str, str] = {
    mr: prof["key"]
    for prof in REGION_PROFILES
    for mr in prof["members"]
}


def get_profile(key: str) -> dict[str, Any] | None:
    """권역 key 로 프로필을 찾는다 (없으면 None)."""
    return next((p for p in REGION_PROFILES if p["key"] == key), None)


def region_keywords_for_music_region(music_region: str) -> list[str]:
    """place.music_region 이 속한 권역의 음악 특징 키워드를 돌려준다 (임베딩 강화용)."""
    key = PLACE_REGION_GROUP.get(music_region)
    prof = get_profile(key) if key else None
    return list(prof["keywords"]) if prof else []
