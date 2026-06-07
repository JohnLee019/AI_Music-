"""국립국악원 국악디지털음원(악구) 수집 스크립트 (prep, 1회성) — sample_loop 트랙군.

데이터: data.go.kr/data/15097515 → apis.data.go.kr/1371034/phrasedataview2/view
- 전통국악 '악구(phrase)' 13,563건. 응답은 **XML**. 성공 resultCode="00".
- 각 항목에 **wav_file_path**(apis.gugak.go.kr 직링크)가 있어 실제 재생/편집용 샘플로 쓸 수 있다.
- 완성곡(full_track) 아님 → asset_kind="sample_loop" (AGENTS.md §5.2/§5.3, 편집용 소스·악기 태그).
- 임베딩은 generate_data.py 가 채운다. 출력: data/raw/gugak_samples.json.

⚠️ 인증키 인코딩(중요): 이 API 는 **이중 인코딩된(=Encoding) 키**를 요구한다.
   (TourAPI 는 Decoding 키를 그대로 썼지만, 이 API 는 quote(quote(key)) 형태여야 200.)
   게이트웨이가 간헐적으로 403/500/502 를 내므로 재시도(_request)로 흡수한다.

사용:
  cd backend && python prep/collect_gugak_samples.py --probe   # 응답 구조 확인
  cd backend && python prep/collect_gugak_samples.py           # 수집
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── 엔드포인트 (확인됨) ─────────────────────────────────
BASE_URL = "https://apis.data.go.kr/1371034"
OPERATION = "phrasedataview2/view"     # 악구 목록조회 (/view 필수)
ASSET_LABEL = "악구"

# ── 악기 코드 → 이름 (instr_cd 열거로 악기 다양성 확보; 영문 'by X' 로 검증된 8종) ──
# 나머지 코드는 가창(가곡·시조 등)·사물놀이 타악으로 'by X' 태그가 없어 신뢰 식별 불가 → 제외.
INSTR_CD_NAME = {
    "PHINST0001": "가야금", "PHINST0002": "거문고", "PHINST0003": "해금",
    "PHINST0006": "피리",   "PHINST0007": "태평소", "PHINST0008": "대금",
    "PHINST0010": "단소",   "PHINST0022": "장구",
}

# ── 수집 정책 (AGENTS.md §2·§11: '노출하는 것만') ─────────
NUM_OF_ROWS = 100
MAX_PAGES = 6              # 악기당 탐색 페이지 상한
PER_INSTRUMENT_CAP = 5     # 악기당 상한 → 악기 다양성 확보 (B-1 악기 태그 시각화용)
MAX_TOTAL = 60             # 전체 상한 (8악기 × 5 ≈ 40)
REQUEST_TIMEOUT = 20
PER_CALL_SLEEP = 0.3
MAX_RETRIES = 4            # 게이트웨이 간헐 오류(403/500/502) 흡수
RETRY_SLEEP = 1.5

OUTPUT_PATH = Path(__file__).resolve().parents[1].parent / "data" / "raw" / "gugak_samples.json"
LICENSE_TYPE = "공공누리 제1유형"
GUGAK_HOME = "https://www.gugak.go.kr/digitaleum"

# 악기명 추출용 (phrs_desc_kor 예: "상사별곡 장구"). 긴 이름 우선 매칭.
GUGAK_INSTRUMENTS = sorted([
    "가야금", "거문고", "해금", "아쟁", "양금", "대금", "중금", "소금", "단소",
    "향피리", "세피리", "당피리", "피리", "태평소", "나발", "나각", "생황",
    "장구", "장고", "좌고", "용고", "북", "편종", "편경", "방향", "운라",
    "꽹과리", "징", "자바라", "바라", "박", "축", "어", "비파", "월금", "공후",
], key=len, reverse=True)

# 영어 설명(phrs_desc_eng 예: "... by gayageum") 로마자 → 한글 악기명 폴백.
ENG_INSTRUMENTS = {
    "gayageum": "가야금", "geomungo": "거문고", "haegeum": "해금", "ajaeng": "아쟁",
    "yanggeum": "양금", "daegeum": "대금", "junggeum": "중금", "sogeum": "소금",
    "danso": "단소", "piri": "피리", "taepyeongso": "태평소", "saenghwang": "생황",
    "jang-gu": "장구", "janggu": "장구", "janggo": "장구", "buk": "북",
    "kkwaenggwari": "꽹과리", "jing": "징", "bipa": "비파",
    "pyeonjong": "편종", "pyeongyeong": "편경", "nabal": "나발", "nagak": "나각",
}


def _service_key_wire() -> str:
    """Decoding 키를 이중 인코딩해 서버가 Encoding 키로 받게 만든다."""
    raw = os.environ.get("GUGAK_API_KEY") or os.environ.get("DATA_API_KEY")
    if not raw:
        raise RuntimeError("GUGAK_API_KEY 또는 DATA_API_KEY(.env)가 비어 있습니다.")
    return urllib.parse.quote(urllib.parse.quote(raw, safe=""), safe="")


def _request(page: int, instr_cd: Optional[str] = None) -> Optional[str]:
    """한 페이지 XML 을 가져온다. instr_cd 로 악기 필터. 간헐 오류는 재시도로 흡수."""
    qs = (f"serviceKey={_service_key_wire()}"
          f"&numOfRows={NUM_OF_ROWS}&pageNo={page}")
    if instr_cd:
        qs += f"&instr_cd={instr_cd}"
    url = f"{BASE_URL}/{OPERATION}?{qs}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = httpx.get(url, timeout=REQUEST_TIMEOUT,
                          headers={"User-Agent": "GugakPlace-prep"})
            if r.status_code == 200 and "<response" in r.text:
                return r.text
            print(f"  [retry {attempt}/{MAX_RETRIES}] p{page} HTTP {r.status_code}")
        except httpx.HTTPError as exc:
            print(f"  [retry {attempt}/{MAX_RETRIES}] p{page} {type(exc).__name__}")
        time.sleep(RETRY_SLEEP)
    return None


def _txt(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    val = (el.text or "").strip() if el is not None else ""
    return "" if val.upper() == "NULL" else val


def _parse_items(xml_text: str) -> list[ET.Element]:
    root = ET.fromstring(xml_text)
    code = root.findtext("./header/resultCode", "")
    if code not in ("00", "0000"):
        print(f"  [warn] resultCode={code} msg={root.findtext('./header/resultMsg','')}")
        return []
    return root.findall("./body/items/item")


def _extract_instrument(desc_kor: str, desc_eng: str) -> Optional[str]:
    """한글 설명 → 영어 설명 순으로 악기명 추출. 둘 다 실패하면 None(=수집 제외)."""
    for ins in GUGAK_INSTRUMENTS:
        if ins in desc_kor:
            return "장구" if ins == "장고" else ins
    low = desc_eng.lower()
    for eng, kor in ENG_INSTRUMENTS.items():
        if eng in low:
            return kor
    return None   # 코드(PHINST..)만 있는 항목은 악기 태그에 무의미 → 제외


def build_track(item: ET.Element, instrument: Optional[str] = None) -> Optional[dict[str, Any]]:
    audio_url = _txt(item, "wav_file_path")
    phrase_cd = _txt(item, "phrase_cd")
    if not audio_url or not phrase_cd:
        return None
    desc_kor = _txt(item, "phrs_desc_kor")
    # instr_cd 열거 경로는 검증된 이름을 강제 주입(빈 설명 샘플도 구제). 아니면 설명에서 추출.
    if instrument is None:
        instrument = _extract_instrument(desc_kor, _txt(item, "phrs_desc_eng"))
        if not instrument:
            return None   # 악기 미확인 항목 제외 (코드만 있는 데이터)
    name = _txt(item, "phrs_nm_kor") or phrase_cd
    rhythm = _txt(item, "rhythm")
    trad_key = _txt(item, "traditional_key")
    area = _txt(item, "area")
    sid = phrase_cd.replace("-", "_")
    mood = [m for m in (trad_key,) if m]            # 전통조(계면조 등)를 mood 로
    title = f"{name} ({instrument})"
    return {
        "id": f"gugak_{sid}",
        "title": title,
        "genre": "국악 샘플",
        "sub_genre": ASSET_LABEL,                    # 악구
        "region": "전국",                            # 권역 비특정 → 의미·태그로 매칭
        "instruments": [instrument],
        "mood": mood,
        "description": (f"국립국악원 국악디지털음원 {ASSET_LABEL} 샘플. 악기: {instrument}"
                        + (f", 장단: {rhythm}" if rhythm else "")
                        + (f", 전통조: {trad_key}" if trad_key else "")
                        + (f", 지역: {area}" if area else "") + "."),
        "keywords": f"국악,샘플,편집소스,{instrument},{ASSET_LABEL}"
                    + (f",{rhythm}" if rhythm else "") + (f",{trad_key}" if trad_key else ""),
        "audio_path": f"/audio/gugak_{sid}.mp3",  # 소스는 wav, download_audio 가 mp3 로 변환
        "audio_source_url": audio_url,
        "asset_kind": "sample_loop",                 # ★ 편집용 (full_track 아님)
        "source": "국립국악원",
        "source_url": GUGAK_HOME,
        "license_type": LICENSE_TYPE,
        "license_note": "국립국악원 국악디지털음원 (data.go.kr/15097515)",
        "is_derivative_allowed": True,
        # §5.3: 발행연도·기관명·홈페이지URL·라이선스
        "attribution_text": f"{name} / 국립국악원(2020) / {GUGAK_HOME} / {LICENSE_TYPE}(출처표시)",
    }


def probe() -> None:
    print(f"probe: {BASE_URL}/{OPERATION}")
    xml_text = _request(1)
    if not xml_text:
        print("  응답 없음 — 활용신청/네트워크 확인.")
        return
    items = _parse_items(xml_text)
    print(f"  items: {len(items)}")
    if items:
        first = items[0]
        print("  첫 항목 태그:", [c.tag for c in first])
        print("  build_track:", json.dumps(build_track(first), ensure_ascii=False)[:500])


def collect() -> list[dict[str, Any]]:
    """악기 코드(instr_cd)를 열거해 악기별로 균형 있게 sample_loop 을 모은다."""
    seen: set[str] = set()
    per_inst: dict[str, int] = {}
    tracks: list[dict[str, Any]] = []
    for code, inst_name in INSTR_CD_NAME.items():
        if len(tracks) >= MAX_TOTAL:
            break
        kept = 0
        for page in range(1, MAX_PAGES + 1):
            if kept >= PER_INSTRUMENT_CAP:
                break
            print(f"[{inst_name}] {code} page={page} (수집 {len(tracks)})")
            xml_text = _request(page, instr_cd=code)
            time.sleep(PER_CALL_SLEEP)
            if not xml_text:
                break
            items = _parse_items(xml_text)
            if not items:
                break
            for item in items:
                if kept >= PER_INSTRUMENT_CAP:
                    break
                track = build_track(item, instrument=inst_name)  # 검증된 이름 강제 주입
                if not track or track["id"] in seen:
                    continue
                seen.add(track["id"])
                per_inst[inst_name] = per_inst.get(inst_name, 0) + 1
                kept += 1
                tracks.append(track)
    print("악기 분포:", per_inst)
    return tracks


def main() -> None:
    if "--probe" in sys.argv:
        probe()
        return
    tracks = collect()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(tracks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n수집 완료: {len(tracks)}개 sample_loop -> {OUTPUT_PATH}")
    print("다음: python prep/generate_data.py (임베딩) + download_audio.py (오디오)")


if __name__ == "__main__":
    main()
