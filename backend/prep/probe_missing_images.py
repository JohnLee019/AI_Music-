"""(prep, 1회성 진단) image_url 이 빈 장소에 대해 detailImage2 로 사진 존재 여부를 확인한다.

collect_places.py 는 detailCommon2.firstimage 만 본다. 그게 비어도 detailImage2
(이미지 갤러리 전용 오퍼레이션)에는 사진이 있는 경우가 많다. 이 스크립트는
data/places.json 에서 image_url 이 빈 tour_* 장소만 골라 detailImage2 를 호출,
공공누리 사진이 있는지 / 있다면 URL·저작권코드를 출력한다 (places.json 은 수정 안 함).

사용:
  cd backend && python prep/probe_missing_images.py
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
PLACES_PATH = Path(__file__).resolve().parents[2] / "data" / "places.json"
REQUEST_TIMEOUT = 10
PER_CALL_SLEEP = 0.2


def _get(operation: str, params: dict[str, Any]) -> Optional[dict[str, Any]]:
    service_key = os.environ.get("TOURAPI_KEY") or os.environ.get("DATA_API_KEY")
    if not service_key:
        raise RuntimeError("TOURAPI_KEY 또는 DATA_API_KEY(.env, Decoding 키)가 비어 있습니다.")
    full = {
        "serviceKey": service_key,
        "MobileOS": "ETC",
        "MobileApp": "GugakPlace",
        "_type": "json",
        **params,
    }
    try:
        resp = httpx.get(f"{BASE_URL}/{operation}", params=full, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"  [warn] {operation} 호출 실패: {exc}")
        return None
    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") != "0000":
        print(f"  [warn] {operation} resultCode={header.get('resultCode')} msg={header.get('resultMsg')}")
        return None
    return data


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("response", {}).get("body", {}).get("items", "")
    if not items:
        return []
    item = items.get("item", [])
    return item if isinstance(item, list) else [item]


def fetch_images(content_id: str) -> list[dict[str, str]]:
    """detailImage2 로 사진 목록 조회. 각 항목: originimgurl, smallimageurl, cpyrhtDivCd."""
    data = _get("detailImage2", {
        "contentId": content_id,
        "imageYN": "Y",       # 콘텐츠 이미지(갤러리)
        "numOfRows": 10,
        "pageNo": 1,
    })
    if not data:
        return []
    out = []
    for it in _items(data):
        url = (it.get("originimgurl") or it.get("smallimageurl") or "").strip()
        if url:
            out.append({"url": url, "cpyrhtDivCd": (it.get("cpyrhtDivCd") or "").strip()})
    return out


def main() -> None:
    doc = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    missing = [p for p in doc["places"] if not p.get("image_url") and str(p.get("id", "")).startswith("tour_")]
    print(f"image_url 비어있는 tour_* 장소: {len(missing)}곳\n")

    found, none = [], []
    for p in missing:
        content_id = p["id"].replace("tour_", "")
        imgs = fetch_images(content_id)
        time.sleep(PER_CALL_SLEEP)
        if imgs:
            found.append((p, imgs))
            print(f"[O] {p['name']} (cid={content_id}) -> {len(imgs)}장")
            print(f"     {imgs[0]['url']}  (저작권 {imgs[0]['cpyrhtDivCd'] or '미표기'})")
        else:
            none.append(p)
            print(f"[X] {p['name']} (cid={content_id}) -> 사진 없음")

    print(f"\n요약: detailImage2 로 사진 발견 {len(found)}곳 / 여전히 없음 {len(none)}곳")
    if none:
        print("여전히 없음:", ", ".join(p["name"] for p in none))


if __name__ == "__main__":
    main()
