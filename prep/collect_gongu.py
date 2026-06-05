"""
collect_gongu.py — 공유마당(공유저작물) 자체 API 음원 수집 스크립트 (prep, 1회성)

이 스크립트는 GugakPlace의 AGENTS.md §2/§5 원칙에 따라 "수집용"이다.
런타임 경로가 아니라, 오프라인에서 한 번 돌려 data/raw/ 에 원본을 받고
data/raw/gongu_sound.json 으로 1차 정규화한다. (이후 build_tracks 단계에서
임베딩·최종 tracks.json 으로 가공)

────────────────────────────────────────────────────────────────────
사전 준비 (한 번만)
────────────────────────────────────────────────────────────────────
1) 공유마당 로그인 → API Key 발급:
     https://gongu.copyright.or.kr/gongu/useReqst/apiKey/forInsert.do?menuNo=200245
2) 프로젝트 루트 .env 에 발급키를 넣는다:
     GONGU_API_KEY=발급받은키
   (요청주소/파라미터는 API 정의서 기준으로 아래에 이미 하드코딩되어 있다.
    필요하면 GONGU_API_URL 로 덮어쓸 수 있다.)

────────────────────────────────────────────────────────────────────
API 정의서 핵심 (검증 완료)
────────────────────────────────────────────────────────────────────
· 목록 검색 URL : https://gongu.copyright.or.kr/gongu/wrt/wrtApi/search.json
  - 반드시 https (http 는 503)
  - 응답은 JSON. 항목 배열은 resultList, 전체 건수는 resultCnt
· 상세 검색 URL : https://gongu.copyright.or.kr/gongu/wrt/wrtApi/searchDetail.json (wrtSn 필요)
· 요청 변수 : apiKey(필수), keyword, pageUnit, pageIndex,
              wrtTy(저작물유형: 음악=10002), wrtFileTy(파일유형: 음원=03),
              licenseCd(콤마구분), startDt/endDt(yyyyMMdd)
· 음원 파일 다운로드 URL 은 이 API 가 제공하지 않는다.
  → 실제 음원은 source_url(상세페이지)에서 받아야 한다. (API 한계)

────────────────────────────────────────────────────────────────────
사용 순서
────────────────────────────────────────────────────────────────────
# 1단계: 실제 응답 JSON 1페이지 확인 (필드/구조 점검용)
python -m prep.collect_gongu --discover

# 2단계: 본 수집 (국악/전통음악/관현악/효과음 키워드 + 음원 파일)
python -m prep.collect_gongu

# (옵션) 항목마다 상세 API를 호출해 분류명(clNm)·라이선스명까지 보강 — 느림
python -m prep.collect_gongu --detail

의존성:  pip install requests python-dotenv
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv 없으면 OS 환경변수만 사용
    pass

# ──────────────────────────────────────────────────────────────────
# 설정 (API 정의서 기준 — 검증 완료)
# ──────────────────────────────────────────────────────────────────
SEARCH_URL = os.getenv(
    "GONGU_API_URL",
    "https://gongu.copyright.or.kr/gongu/wrt/wrtApi/search.json",
)
DETAIL_URL = os.getenv(
    "GONGU_DETAIL_URL",
    "https://gongu.copyright.or.kr/gongu/wrt/wrtApi/searchDetail.json",
)
API_KEY = os.getenv("GONGU_API_KEY", "")

OUT_DIR = Path("data/raw")
RAW_JSON_PATH = OUT_DIR / "gongu_sound_raw.json"   # 디버그용 마지막 응답 원본
OUT_JSON_PATH = OUT_DIR / "gongu_sound.json"       # 1차 정규화 결과

# 저작물 파일유형: 음원=03 (정의서 COM102)
WRT_FILE_TY_AUDIO = "03"

# 음원 재생/다운로드 엔드포인트 (상세페이지 HTML 에서 발견 — 직접 MP3 반환).
#   GET …/wrtFileMediaPlay.do?wrtSn={wrtSn}&fileSn=1  →  audio/mpeg(MP3) 바이트
#   wrtSn 만으로 결정적이라 추가 호출 없이 audio_url 을 채울 수 있다.
MEDIA_PLAY_URL = "https://gongu.copyright.or.kr/gongu/wrt/cmmn/wrtFileMediaPlay.do"
AUDIO_DIR = Path("data/raw/audio")

# 수집 대상: 키워드로 검색한다 (자체 API 에 depth2ClSn 카테고리 파라미터는 없음).
#   ⚠️ 키워드에 공백이 들어가면 서버가 500 을 반환한다 → 반드시 한 단어(붙여쓰기).
TARGET_KEYWORDS = [
    "국악", "전통음악", "관현악", "국악관현악",
    "산조", "판소리", "민요", "사물놀이", "농악",
    "가야금", "거문고", "대금",
]

PAGE_SIZE = 50
MAX_PAGES = 200          # 키워드당 안전 상한
REQUEST_TIMEOUT = 20
SLEEP_BETWEEN = 0.4      # 서버 예의상 호출 간 대기(초)
MAX_RETRY = 3

# 응답 JSON 필드 매핑 (search.json — 라이브 검증 완료)
RESULT_LIST_KEY = "resultList"
COUNT_KEY = "resultCnt"

# 검색어 하이라이트 태그 (<!HS>키워드<!HE>) 제거용
_HL_RE = re.compile(r"<!H[SE]>")


# ──────────────────────────────────────────────────────────────────
# 라이선스 코드표 (API 정의서 COM088 + KOGL/CCL 규칙)
#   code -> (표시명, commercial_ok, derivative_ok)
#   None = 자동판정 불가 → 상세페이지로 수동 검증 필요(§5.5)
# ──────────────────────────────────────────────────────────────────
LICENSE_TABLE: dict[str, tuple[str, bool | None, bool | None]] = {
    "01": ("공공누리 제1유형(출처표시)", True, True),
    "02": ("공공누리 제2유형(출처표시+상업금지)", False, True),
    "03": ("공공누리 제3유형(출처표시+변경금지)", True, False),
    "04": ("공공누리 제4유형(상업금지+변경금지)", False, False),
    "20": ("CCL", None, None),            # 세부유형 불명 → 보수적
    "21": ("CCL(BY)", True, True),
    "22": ("CCL(BY-ND)", True, False),
    "23": ("CCL(BY-SA)", True, True),
    "24": ("CCL(BY-NC)", False, True),
    "25": ("CCL(BY-NC-ND)", False, False),
    "26": ("CCL(BY-NC-SA)", False, True),
    "27": ("기타", None, None),
    "97": ("이용허락(기타)", None, None),
    "98": ("이용허락(직접계약 등)", None, None),
    "99": ("만료/공유저작물(추정)", None, None),
}


def derive_license(license_code: str) -> dict[str, Any]:
    """라이선스 코드(예: '21') → license_type / commercial_ok / derivative_ok / creator_safe."""
    name, commercial_ok, derivative_ok = LICENSE_TABLE.get(
        (license_code or "").strip(), (f"미상(code={license_code})", None, None)
    )
    creator_safe = (commercial_ok is True) and (derivative_ok is True)
    return {
        "license_code": license_code,
        "license_type": name,
        "commercial_ok": commercial_ok,
        "derivative_ok": derivative_ok,
        "creator_safe": creator_safe,  # 수익화+편집 동시 안전
    }


def _clean(text: str) -> str:
    """검색어 하이라이트 태그 제거 + 공백 정리."""
    return _HL_RE.sub("", (text or "")).strip()


def media_url(wrt_sn: str, file_sn: int = 1) -> str:
    """wrtSn → 직접 재생/다운로드 가능한 음원(MP3) URL."""
    if not wrt_sn:
        return ""
    return f"{MEDIA_PLAY_URL}?wrtSn={wrt_sn}&fileSn={file_sn}"


# ──────────────────────────────────────────────────────────────────
# HTTP
# ──────────────────────────────────────────────────────────────────
def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET 호출 → JSON dict 반환. 재시도 포함."""
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  ! 호출 실패(시도 {attempt}/{MAX_RETRY}): {e}", file=sys.stderr)
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"호출 반복 실패: {last_err}")


def fetch_page(keyword: str, page: int) -> dict[str, Any]:
    """음원 파일유형 + 키워드로 한 페이지 검색."""
    params = {
        "apiKey": API_KEY,
        "keyword": keyword,
        "wrtFileTy": WRT_FILE_TY_AUDIO,
        "pageUnit": PAGE_SIZE,
        "pageIndex": page,
    }
    return _get_json(SEARCH_URL, params)


def fetch_detail(wrt_sn: str) -> dict[str, Any]:
    """상세 API로 분류명(clNm)·라이선스명·태그 보강."""
    return _get_json(DETAIL_URL, {"apiKey": API_KEY, "wrtSn": wrt_sn})


def normalize_item(it: dict[str, Any], keyword: str) -> dict[str, Any]:
    """search.json 한 항목 → 내부 표준 레코드."""
    lic = derive_license(str(it.get("licenseCd", "")))
    return {
        "source": "공유마당",
        "search_keyword": keyword,
        "source_id": str(it.get("wrtSn", "")),
        "title": _clean(it.get("orginSj", "")),
        "author": _clean(it.get("authorListNm", "")),
        "tags": _clean(it.get("tagNmList", "")),
        "wrt_type": it.get("wrtTy", ""),          # 10002 = 음악
        **lic,
        "audio_url": media_url(str(it.get("wrtSn", ""))),  # 직접 재생/다운로드(MP3)
        "source_url": it.get("linkUrl", ""),      # 상세페이지
        "thumb_url": it.get("thumbUrl", ""),
        "reg_dt": it.get("regDt", ""),
        "_raw": it,
    }


# ──────────────────────────────────────────────────────────────────
# 모드
# ──────────────────────────────────────────────────────────────────
def discover() -> None:
    """첫 키워드 1페이지 응답 JSON 을 그대로 저장/출력(구조 점검용)."""
    _require_config()
    kw = TARGET_KEYWORDS[0]
    print(f"=== DISCOVER: '{kw}' 음원 1페이지 원본 응답 ===\n")
    data = fetch_page(kw, 1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_JSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    items = data.get(RESULT_LIST_KEY, []) or []
    print(f"resultCode = {data.get('resultCode')}")
    print(f"{COUNT_KEY} = {data.get(COUNT_KEY)}  (이 키워드 전체 건수)")
    print(f"이 페이지 항목 수 = {len(items)}")
    if items:
        print("\n[항목 0] 표준화 결과:")
        print(json.dumps(normalize_item(items[0], kw), ensure_ascii=False, indent=2))
    print(f"\n... (원본 전체는 {RAW_JSON_PATH} 에 저장)")


def collect(with_detail: bool = False) -> None:
    """타깃 키워드 전체를 페이징 수집 → 정규화 → dedupe → JSON 저장."""
    _require_config()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for kw in TARGET_KEYWORDS:
        # 한 키워드가 실패해도(예: 서버 500) 전체 수집을 버리지 않는다.
        try:
            first = fetch_page(kw, 1)
        except Exception as e:  # noqa: BLE001
            print(f"[{kw}] 첫 페이지 실패 → 건너뜀: {e}", file=sys.stderr)
            continue
        total = first.get(COUNT_KEY)
        print(f"[{kw}] 수집 시작 (전체 {total}건)")
        page = 1
        while page <= MAX_PAGES:
            try:
                data = first if page == 1 else fetch_page(kw, page)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {page}페이지 실패 → 이 키워드 중단: {e}", file=sys.stderr)
                break
            items = data.get(RESULT_LIST_KEY, []) or []
            if not items:
                print(f"  - {page}페이지에서 항목 없음 → 키워드 종료")
                break
            added = 0
            for it in items:
                rec = normalize_item(it, kw)
                sid = rec["source_id"] or rec["source_url"] or rec["title"]
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                if with_detail and rec["source_id"]:
                    _enrich(rec)
                    time.sleep(SLEEP_BETWEEN)
                results.append(rec)
                added += 1
            print(f"  - {page}페이지: {added}건 추가 (누적 {len(results)})")
            page += 1
            time.sleep(SLEEP_BETWEEN)

    OUT_JSON_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    safe = sum(1 for r in results if r["creator_safe"])
    unknown = sum(1 for r in results if r["commercial_ok"] is None or r["derivative_ok"] is None)
    print(f"\n완료: 총 {len(results)}건 → {OUT_JSON_PATH}")
    print(f"  · creator_safe(수익화+편집 안전): {safe}건")
    print(f"  · 라이선스 자동판정 불가(None): {unknown}건 → source_url 원문으로 수동 검증(§5.5)")
    print(f"  · audio_url 채움(직접 MP3) → 실제 파일은 `--download` 로 받기")


def _enrich(rec: dict[str, Any]) -> None:
    """상세 API로 분류명(clNm)·라이선스명·태그를 보강(실패해도 무시)."""
    try:
        d = fetch_detail(rec["source_id"])
    except Exception as e:  # noqa: BLE001
        print(f"  ! 상세 보강 실패(wrtSn={rec['source_id']}): {e}", file=sys.stderr)
        return
    rec["category"] = _clean(d.get("clNm", ""))
    lic = d.get("licenseCd")
    if isinstance(lic, dict) and lic.get("cdNm"):
        rec["license_type"] = lic["cdNm"]
    if d.get("tagNm"):
        rec["tags"] = _clean(d["tagNm"])
    rec["gongu_link"] = d.get("gonguLinkUrl", "")


def _require_config() -> None:
    if not API_KEY:
        print("환경변수 누락: GONGU_API_KEY — .env 를 확인하세요.", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# 음원 파일 다운로드
# ──────────────────────────────────────────────────────────────────
_AUDIO_MAGIC = (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2",  # MP3
                b"RIFF", b"OggS", b"fLaC")                      # WAV/OGG/FLAC


def _guess_ext(content_type: str, head: bytes) -> str:
    ct = (content_type or "").lower()
    if "mpeg" in ct or "mp3" in ct or head.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return ".mp3"
    if "wav" in ct or head.startswith(b"RIFF"):
        return ".wav"
    if "ogg" in ct or head.startswith(b"OggS"):
        return ".ogg"
    if "flac" in ct or head.startswith(b"fLaC"):
        return ".flac"
    return ".mp3"  # 공유마당 음원은 사실상 MP3


def download(limit: int | None = None, safe_only: bool = False) -> None:
    """gongu_sound.json 을 읽어 audio_url 의 실제 음원 파일을 내려받는다.

    · data/raw/audio/{source_id}.{ext} 로 저장
    · 이미 받은 파일은 건너뜀(이어받기/재실행 안전)
    · safe_only=True 면 creator_safe 항목만 받음
    """
    if not OUT_JSON_PATH.exists():
        print(f"{OUT_JSON_PATH} 없음 — 먼저 수집을 실행하세요.", file=sys.stderr)
        sys.exit(1)
    records = json.loads(OUT_JSON_PATH.read_text(encoding="utf-8"))
    if safe_only:
        records = [r for r in records if r.get("creator_safe")]
    if limit:
        records = records[:limit]

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})

    ok = skipped = failed = 0
    total = len(records)
    for i, rec in enumerate(records, 1):
        sid, url = rec.get("source_id"), rec.get("audio_url")
        if not sid or not url:
            failed += 1
            continue
        # 이미 받은 파일(확장자 무관) 있으면 skip
        if any(AUDIO_DIR.glob(f"{sid}.*")):
            skipped += 1
            continue
        try:
            r = sess.get(url, headers={"Referer": rec.get("source_url", "")},
                         timeout=REQUEST_TIMEOUT, stream=True)
            r.raise_for_status()
            it = r.iter_content(8192)
            head = next(it, b"")
            if not head.startswith(_AUDIO_MAGIC):
                # 음원이 아니라 HTML 오류페이지 등 → 실패 처리
                raise ValueError(f"음원 아님(머리={head[:8]!r})")
            ext = _guess_ext(r.headers.get("content-type", ""), head)
            tmp = AUDIO_DIR / f"{sid}{ext}.part"
            with open(tmp, "wb") as f:
                f.write(head)
                for chunk in it:
                    f.write(chunk)
            tmp.rename(AUDIO_DIR / f"{sid}{ext}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ! 다운로드 실패(wrtSn={sid}): {e}", file=sys.stderr)
        if i % 25 == 0 or i == total:
            print(f"  [{i}/{total}] 성공 {ok} · 건너뜀 {skipped} · 실패 {failed}")
        time.sleep(SLEEP_BETWEEN)

    print(f"\n다운로드 완료 → {AUDIO_DIR}")
    print(f"  · 성공 {ok} · 건너뜀(기존) {skipped} · 실패 {failed} / 대상 {total}건")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="공유마당 음원 수집 (prep)")
    ap.add_argument("--discover", action="store_true",
                    help="원본 JSON 1페이지를 저장/출력해 구조 점검")
    ap.add_argument("--detail", action="store_true",
                    help="항목마다 상세 API 호출로 분류명/라이선스명 보강(느림)")
    ap.add_argument("--download", action="store_true",
                    help="gongu_sound.json 의 audio_url 음원 파일을 data/raw/audio/ 로 받기")
    ap.add_argument("--safe-only", action="store_true",
                    help="--download 시 creator_safe 항목만 받기")
    ap.add_argument("--limit", type=int, default=None,
                    help="--download 시 받을 최대 건수(테스트용)")
    args = ap.parse_args()
    if args.discover:
        discover()
    elif args.download:
        download(limit=args.limit, safe_only=args.safe_only)
    else:
        collect(with_detail=args.detail)
