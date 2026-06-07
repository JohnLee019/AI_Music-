"""(prep, 1회성) probe_missing_images.py 로 찾은 detailImage2 사진 3건을 places.json 에 기록.

image_url / image_copyright 두 필드만 갱신한다. embedding 등 나머지 필드는 건드리지 않으며,
키 순서를 보존하기 위해 기존 dict 를 in-place 로 수정 후 그대로 다시 쓴다.

사용:
  cd backend && python prep/patch_recovered_images.py
"""

from __future__ import annotations

import json
from pathlib import Path

PLACES_PATH = Path(__file__).resolve().parents[2] / "data" / "places.json"

# id -> (image_url, image_copyright)  (probe_missing_images.py 출력 결과)
PATCHES = {
    "tour_129125": ("https://tong.visitkorea.or.kr/cms/resource/03/2837903_image2_1.jpg", "Type3"),  # 서산 경주김씨 고택
    "tour_128038": ("https://tong.visitkorea.or.kr/cms/resource/77/3500877_image2_1.jpg", "Type1"),  # 고령 지산동 고분군
    "tour_128786": ("https://tong.visitkorea.or.kr/cms/resource/60/182160_image2_1.jpg", "Type3"),   # 방동리 고구려고분
}


def main() -> None:
    doc = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    updated = []
    for p in doc["places"]:
        patch = PATCHES.get(p.get("id"))
        if patch:
            p["image_url"], p["image_copyright"] = patch
            updated.append(p["name"])
    PLACES_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"갱신 {len(updated)}곳: {', '.join(updated)}")
    remaining = sum(1 for p in doc["places"] if not p.get("image_url"))
    print(f"여전히 image_url 빈 장소: {remaining}곳")


if __name__ == "__main__":
    main()
