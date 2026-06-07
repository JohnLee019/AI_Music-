"""TourAPI(KorService2) 기반 장소 수집 스크립트 (prep, 1회성).

AGENTS.md §2 / §5.1 준수:
- 런타임 경로 아님. backend/prep/에서 수동 실행하는 수집용.
- 임베딩은 하지 않는다. generate_data.py가 hero 장소와 함께 자동 임베딩.
- 출력: data/raw/tourapi_places.json (임베딩 없는 place dict 리스트).

흐름 (한국관광공사 활용매뉴얼 v4.4):
  searchKeyword2 (목록) -> contentid별 detailCommon2 (overview) 2단계 호출.

키:
  .env 의 TOURAPI_KEY(없으면 DATA_API_KEY) 는 data.go.kr **Decoding 키**.
  httpx 가 params dict 를 인코딩하므로 원본(Decoding) 키를 그대로 넘긴다.
  이미 인코딩된 키를 넣으면 이중 인코딩 -> 에러코드 30.

사용:
  cd backend && python prep/collect_places.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

# Windows에서 stdout 리다이렉트 시 기본 cp949 → 한글 인코딩 에러 방지.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# .env 로드 (backend/.env 우선, 없으면 프로젝트 루트 .env)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# rules.py 의 권역 매핑 재사용 (AGENTS.md §5.1: music_region = addr1 -> REGION_MAP)
try:
    from rules import REGION_MAP  # backend/ 를 cwd 로 실행할 때
except ImportError:  # prep/ 안에서 직접 실행하는 경우 대비
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from rules import REGION_MAP

# --- 상수 -----------------------------------------------------------------

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
MOBILE_APP = "GugakPlace"
MOBILE_OS = "ETC"
REQUEST_TIMEOUT = 10  # 초 (AGENTS.md §9: 외부 호출은 항상 타임아웃)
PER_CALL_SLEEP = 0.2  # data.go.kr rate 보호
NUM_OF_ROWS = 50       # 페이지당 결과 수
MAX_PAGES = 5          # 키워드별 최대 페이지 (안전 상한)
PER_KEYWORD_CAP = 30   # 키워드별 수집 상한 — 서원/향교 편중 방지, 8도 균형 (AGENTS.md §2)
MAX_TOTAL = 230        # 전체 상한 — 균형 잡힌 ~200곳 목표, API 일일 한도 보호

OUTPUT_PATH = Path(__file__).resolve().parents[1].parent / "data" / "raw" / "tourapi_places.json"

# 문화색 뚜렷한 장소만 모으는 키워드 (AGENTS.md §5.1).
# 서원/향교가 압도적으로 많아(470/246) 편중되므로, 다양성 키워드(고택·왕릉·읍성·고분·관아·민속촌)를
# 더해 유형·지역 분포를 넓힌다. PER_KEYWORD_CAP 으로 한 유형이 지도를 점령하지 않게 막는다.
KEYWORDS = [
    "한옥마을", "서원", "향교", "민속마을", "전통시장", "고궁", "종갓집",
    "고택", "왕릉", "읍성", "고분", "관아", "민속촌",
]

# 허용할 contenttypeid (allow-list). 키워드가 역·지명을 매칭해 끌려온 상업 POI
# (예: '향교' → '올리브영 양천향교역점'(쇼핑), '향교막국수'(음식점))를 차단한다.
#   12 = 관광지, 14 = 문화시설 → 문화 장소.
# 단, 전통시장은 TourAPI에서 쇼핑(38)으로 분류되므로 해당 키워드에서만 38을 추가 허용.
ALLOW_CONTENT_TYPES: set[str] = {"12", "14"}
MARKET_KEYWORD = "전통시장"
MARKET_CONTENT_TYPES: set[str] = {"38"}  # 쇼핑(전통시장 전용)

# 제목 키워드 -> rules.TYPE_GENRE_WEIGHTS 의 type 키 추론.
# contenttypeid(거친 숫자)만으론 궁궐/한옥마을 구분 불가 -> 제목 기반.
# **type 값은 rules.TYPE_GENRE_WEIGHTS·프론트 TYPE_ICON 과 동일한 한글 키**여야
# _type_score 와 아이콘/배지가 동작한다 (히어로 장소 스키마와 일치).
# 미스 시 "전통명소" (rules 키 없음 -> 유형 점수 0, 지역+의미로 매칭).
GENERIC_TYPE = "전통명소"
TITLE_TYPE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("고궁", "궁궐", "행궁", "왕릉", "릉", "궁"), "궁궐"),  # 왕릉=제례·정악 권장 → 궁궐 가중 재사용
    (("향교", "서원"), "서원"),
    (("사찰",), "사찰"),
    (("시장",), "전통시장"),
    (("민속마을", "민속촌"), "민속마을"),
    (("한옥", "고택", "종갓집"), "한옥마을"),
]

# type 별 cultural_keywords 템플릿 (LLM 불필요, AGENTS.md §5.1)
TYPE_KEYWORD_TEMPLATES: dict[str, list[str]] = {
    "궁궐": ["궁중", "정악", "왕실", "의례"],
    "서원": ["유교", "선비", "제례악", "전통"],
    "사찰": ["사찰", "범패", "영산회상", "고요"],
    "전통시장": ["장터", "사물놀이", "흥겨움", "민속"],
    "민속마을": ["민속", "농악", "공동체", "향토"],
    "한옥마을": ["한옥", "산조", "전통", "고즈넉"],
    GENERIC_TYPE: ["전통", "한국", "고장"],
}


# --- HTTP -----------------------------------------------------------------

def _get(operation: str, params: dict[str, Any]) -> Optional[dict[str, Any]]:
    """KorService2 오퍼레이션 GET 호출. 실패 시 None (폴백은 호출부가 결정)."""
    # TOURAPI_KEY 우선, 없으면 data.go.kr 공통 키(DATA_API_KEY)로 폴백.
    service_key = os.environ.get("TOURAPI_KEY") or os.environ.get("DATA_API_KEY")
    if not service_key:
        raise RuntimeError("TOURAPI_KEY 또는 DATA_API_KEY(.env, Decoding 키)가 비어 있습니다.")

    full = {
        "serviceKey": service_key,  # Decoding 키 원본 -> httpx 가 인코딩
        "MobileOS": MOBILE_OS,
        "MobileApp": MOBILE_APP,
        "_type": "json",
        **params,
    }
    try:
        resp = httpx.get(f"{BASE_URL}/{operation}", params=full, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()  # 키 에러 시 XML 이 와서 여기서 예외 -> 아래 except
    except (httpx.HTTPError, ValueError) as exc:
        print(f"  [warn] {operation} 호출 실패: {exc}")
        return None

    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") != "0000":
        print(f"  [warn] {operation} resultCode={header.get('resultCode')} "
              f"msg={header.get('resultMsg')}")
        return None
    return data


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """body.items.item 을 항상 리스트로 정규화 (단건이면 dict 로 올 수 있음)."""
    items = data.get("response", {}).get("body", {}).get("items", "")
    if not items:  # totalCount=0 이면 items 가 빈 문자열
        return []
    item = items.get("item", [])
    return item if isinstance(item, list) else [item]


# --- 정제 -----------------------------------------------------------------

def infer_type(title: str) -> str:
    for needles, type_key in TITLE_TYPE_RULES:
        if any(n in title for n in needles):
            return type_key
    return GENERIC_TYPE


def infer_music_region(addr1: str) -> Optional[str]:
    """addr1 시도명 -> rules.REGION_MAP 권역. 미스 시 None."""
    for region_name, music_region in REGION_MAP.items():
        if region_name in addr1:
            return music_region
    return None


def build_place(list_item: dict[str, Any], overview: str, image_url: str = "", image_copyright: str = "") -> Optional[dict[str, Any]]:
    """searchKeyword2 항목 + detailCommon2 overview -> places.json 스키마(임베딩 제외)."""
    title = (list_item.get("title") or "").strip()
    addr1 = (list_item.get("addr1") or "").strip()
    try:
        lat = float(list_item["mapy"])  # WGS84 위도
        lng = float(list_item["mapx"])  # WGS84 경도
    except (KeyError, ValueError):
        return None  # 좌표 없는 장소는 지도/매칭에 못 씀 -> 제외

    type_key = infer_type(title)
    return {
        "id": f"tour_{list_item.get('contentid')}",
        "name": title,
        "region": addr1.split()[0] if addr1 else "",
        "music_region": infer_music_region(addr1),  # None 가능 -> generate_data 가 처리
        "type": type_key,
        "lat": lat,
        "lng": lng,
        "description": overview.strip(),
        "cultural_keywords": TYPE_KEYWORD_TEMPLATES.get(type_key, TYPE_KEYWORD_TEMPLATES[GENERIC_TYPE]),
        "source": "한국관광공사 TourAPI(국문) / data.go.kr 15101578",
        "source_url": (
            "https://apis.data.go.kr/B551011/KorService2/detailCommon2"
            f"?contentId={list_item.get('contentid')}"
        ),
        "image_url": image_url,
        "image_copyright": image_copyright,
        # embedding 은 의도적으로 넣지 않음 (generate_data.py 가 채움 — AGENTS.md §5.1)
    }


def fetch_detail(content_id: str) -> tuple[str, str, str]:
    """detailCommon2 로 overview(설명), firstimage(대표 이미지), cpyrhtDivCd(저작권코드) 조회."""
    data = _get("detailCommon2", {"contentId": content_id, "numOfRows": 1, "pageNo": 1})
    if not data:
        return "", "", ""
    items = _items(data)
    if not items:
        return "", "", ""
    item = items[0]
    return (
        (item.get("overview") or "").strip(),
        (item.get("firstimage") or "").strip(),
        (item.get("cpyrhtDivCd") or "").strip()
    )


def _total_count(data: dict[str, Any]) -> int:
    try:
        return int(data.get("response", {}).get("body", {}).get("totalCount", 0) or 0)
    except (TypeError, ValueError):
        return 0


def collect() -> list[dict[str, Any]]:
    """키워드별 페이지네이션 + 상한으로 균형 잡힌 장소를 수집한다.

    - PER_KEYWORD_CAP: 한 키워드(예: 서원 470건)가 데이터셋을 점령하지 못하게 제한 → 8도 균형.
    - MAX_TOTAL: 전체 상한 (API 일일 한도 보호).
    """
    seen: set[str] = set()
    places: list[dict[str, Any]] = []

    for keyword in KEYWORDS:
        if len(places) >= MAX_TOTAL:
            break
        # 전통시장만 쇼핑(38) 허용, 그 외 키워드는 관광지·문화시설(12/14)만.
        allowed_types = ALLOW_CONTENT_TYPES | (
            MARKET_CONTENT_TYPES if keyword == MARKET_KEYWORD else set()
        )
        kept_for_kw = 0
        for page in range(1, MAX_PAGES + 1):
            if kept_for_kw >= PER_KEYWORD_CAP or len(places) >= MAX_TOTAL:
                break
            print(f"[searchKeyword2] keyword={keyword} page={page}")
            data = _get("searchKeyword2", {
                "keyword": keyword,  # httpx 가 인코딩 (국문 키워드 OK)
                "numOfRows": NUM_OF_ROWS,
                "pageNo": page,
                "arrange": "C",  # 수정일순
            })
            time.sleep(PER_CALL_SLEEP)
            if not data:
                break
            items = _items(data)
            if not items:
                break

            for item in items:
                if kept_for_kw >= PER_KEYWORD_CAP or len(places) >= MAX_TOTAL:
                    break
                content_id = str(item.get("contentid", ""))
                if not content_id or content_id in seen:
                    continue
                # 문화 장소(관광지·문화시설)만 허용 — 역·지명 매칭 상업 POI 차단 (Tier 2)
                if str(item.get("contenttypeid", "")) not in allowed_types:
                    continue
                seen.add(content_id)

                overview, img_url, img_cpy = fetch_detail(content_id)
                time.sleep(PER_CALL_SLEEP)
                place = build_place(item, overview, img_url, img_cpy)
                if place:
                    places.append(place)
                    kept_for_kw += 1
                    print(f"  + {place['name']} ({place['type']}, {place['music_region']})")

            # 마지막 페이지 도달 시 다음 키워드로
            if page * NUM_OF_ROWS >= _total_count(data):
                break

    return places


def main() -> None:
    places = collect()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(places, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n수집 완료: {len(places)}곳 -> {OUTPUT_PATH}")
    print("다음: python prep/generate_data.py 가 이 파일을 읽어 임베딩까지 채웁니다.")


if __name__ == "__main__":
    main()
