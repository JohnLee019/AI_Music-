"""
국악방송 WAV 원본에서 앞 30초만 잘라 data/audio/ 에 저장한다.

ffmpeg 의존 없이 순수 파이썬으로 동작한다. 원본이 비압축 PCM WAV(audio_format=1)
이고 서버가 HTTP Range 를 지원하므로:
  1. 앞부분(헤더)만 Range 로 받아 fmt/data 청크 위치·샘플레이트를 파싱
  2. data 청크에서 30초 분량 PCM(byte_rate × 30) 만 Range 로 받음
  3. 최소 WAV(RIFF+fmt+data) 헤더를 새로 써서 로컬에 저장

전체 파일(수십 MB)을 받지 않고 곡당 ~5MB 만 전송한다.

사용: python backend/prep/download_audio.py
tracks.json 의 audio_source_url / audio_path 를 읽어 처리하며, 이미 있으면 건너뛴다.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import urllib.request
from collections import defaultdict

import imageio_ffmpeg  # pip 휠로 ffmpeg 바이너리 번들 (시스템 설치/PATH 불필요)

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Windows에서 stdout 리다이렉트 시 기본 cp949 → ✓/✗ 등 특수문자 인코딩 에러로
# 스크립트가 죽는 것을 방지 (UTF-8 강제).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_PREP_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PREP_DIR, "..", "..", "data")
_AUDIO_DIR = os.path.join(_DATA_DIR, "audio")
_TRACKS_JSON = os.path.join(_DATA_DIR, "tracks.json")

TRIM_SECONDS = 30
MP3_BITRATE = "128k"   # WAV→MP3 변환 비트레이트 (30초 ≈ 0.3~0.5MB → 비압축 대비 ~90% 절감)

# ── 오디오 다운로드 서브셋 (AGENTS.md §2·§11: '실제 노출하는 것만' 받아 리포 용량 보호) ──
# 카탈로그(tracks.json)는 183곡 전부 유지하되, 오디오는 장르별 상한만큼만 받는다.
# 받지 않은 곡은 백엔드가 audio_available=false 로 표시 → 프론트가 '미리듣기 준비중'으로 처리.
# 전체를 받고 싶으면 SUBSET_ENABLED=False.
SUBSET_ENABLED = False
SUBSET_TARGETS: dict[str, int] = {
    "민요": 40,        # 권역 라운드로빈으로 8도 균형
    "정악": 20,        # 수기 8 + 연주곡 일부
    "국악 BGM": 40,    # 전량 — 추천 예약 슬롯에 항상 노출되므로 모두 재생 가능하게
    "국악 샘플": 40,   # 국립국악원 sample_loop (단음·악구, 수집 시)
}
_HEADER_PROBE_BYTES = 8192          # fmt/data 청크를 찾기 위한 앞부분 크기
_UA = "Mozilla/5.0 (GugakPlace prep)"
_HTTP_PARTIAL = 206


def _range_get(url: str, start: int, end: int) -> bytes:
    """[start, end] 바이트(양끝 포함)를 Range 요청으로 가져온다."""
    req = urllib.request.Request(
        url, headers={"Range": f"bytes={start}-{end}", "User-Agent": _UA}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != _HTTP_PARTIAL:
            raise RuntimeError(f"서버가 Range를 지원하지 않음 (status={r.status})")
        return r.read()


def _parse_wav_header(head: bytes) -> tuple[dict, int]:
    """RIFF 청크들을 순회해 fmt 파라미터와 data 청크 시작 바이트를 찾는다.

    Returns: (fmt dict, data_pcm_start_byte)
    """
    if head[0:4] != b"RIFF" or head[8:12] != b"WAVE":
        raise ValueError("RIFF/WAVE 헤더가 아님")

    fmt: dict = {}
    data_start = -1
    off = 12
    while off + 8 <= len(head):
        cid = head[off:off + 4]
        csize = struct.unpack("<I", head[off + 4:off + 8])[0]
        body = off + 8
        if cid == b"fmt ":
            af, ch, sr, br, ba, bits = struct.unpack("<HHIIHH", head[body:body + 16])
            fmt = {
                "audio_format": af, "channels": ch, "sample_rate": sr,
                "byte_rate": br, "block_align": ba, "bits": bits,
            }
        elif cid == b"data":
            data_start = body
            break
        off = body + csize + (csize & 1)  # 청크는 2바이트 정렬 패딩

    if not fmt or data_start < 0:
        raise ValueError("fmt 또는 data 청크를 찾지 못함 (헤더 프로브 크기 부족 가능)")
    if fmt["audio_format"] != 1:
        raise ValueError(f"비압축 PCM이 아님 (audio_format={fmt['audio_format']})")
    return fmt, data_start


def _build_wav(fmt: dict, pcm: bytes) -> bytes:
    """fmt + PCM 으로 최소 WAV 바이트열을 만든다."""
    fmt_chunk = struct.pack(
        "<HHIIHH",
        fmt["audio_format"], fmt["channels"], fmt["sample_rate"],
        fmt["byte_rate"], fmt["block_align"], fmt["bits"],
    )
    data_chunk = b"data" + struct.pack("<I", len(pcm)) + pcm
    fmt_full = b"fmt " + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
    riff_body = b"WAVE" + fmt_full + data_chunk
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


def trim_remote_wav(url: str, out_path: str, seconds: int = TRIM_SECONDS) -> None:
    """원격 WAV 의 앞 seconds 초를 받아 out_path 에 저장한다."""
    head = _range_get(url, 0, _HEADER_PROBE_BYTES - 1)
    fmt, data_start = _parse_wav_header(head)

    want_bytes = fmt["byte_rate"] * seconds
    # block_align 경계로 정렬 (샘플 중간에서 자르지 않도록)
    want_bytes -= want_bytes % fmt["block_align"]

    pcm = _range_get(url, data_start, data_start + want_bytes - 1)
    wav = _build_wav(fmt, pcm)
    with open(out_path, "wb") as f:
        f.write(wav)


def download_full(url: str, out_path: str) -> None:
    """오디오를 그대로 내려받는다."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if not data:
        raise RuntimeError("빈 응답 (다운로드 불가)")
    with open(out_path, "wb") as f:
        f.write(data)


def _transcode_to_mp3(in_path: str, out_path: str, seconds: int = TRIM_SECONDS) -> None:
    """ffmpeg(번들 바이너리)로 WAV→MP3 변환. 어떤 입력(16/24bit·float·모노/스테레오)도 처리,
    앞 seconds 초로 캡. 비압축 WAV 대비 ~90% 용량 절감."""
    proc = subprocess.run(
        [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", in_path, "-t", str(seconds),
         "-codec:a", "libmp3lame", "-b:a", MP3_BITRATE, out_path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        raise RuntimeError(f"ffmpeg 변환 실패: {proc.stderr.strip()[:200]}")


def fetch_wav_as_mp3(url: str, out_path: str) -> None:
    """원격 WAV 의 앞 30초를 받아(Range, 실패 시 전체) MP3 로 변환 저장한다."""
    tmp = out_path + ".tmp.wav"
    try:
        try:
            trim_remote_wav(url, tmp)          # PCM(16/24bit): Range 30초 트림
        except Exception:
            download_full(url, tmp)            # float(fmt3)/Range 미지원: 전체 받고 ffmpeg 가 -t 로 컷
        _transcode_to_mp3(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _load_tracks() -> list[dict]:
    with open(_TRACKS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data["tracks"] if isinstance(data, dict) else data


def _select_for_download(tracks: list[dict]) -> list[dict]:
    """장르별 상한으로 균형 잡힌 다운로드 서브셋을 고른다 (민요는 권역 라운드로빈)."""
    if not SUBSET_ENABLED:
        return tracks

    by_genre: dict[str, list[dict]] = defaultdict(list)
    for t in tracks:
        by_genre[t.get("genre", "")].append(t)

    selected: list[dict] = []
    for genre, cap in SUBSET_TARGETS.items():
        pool = by_genre.get(genre, [])
        if genre == "민요":
            # 권역별 버킷을 라운드로빈으로 뽑아 8도 균형 유지
            buckets = [list(v) for v in _group_by_region(pool).values()]
            picked: list[dict] = []
            while len(picked) < cap:
                progressed = False
                for b in buckets:
                    if b and len(picked) < cap:
                        picked.append(b.pop(0))
                        progressed = True
                if not progressed:
                    break
            selected.extend(picked)
        else:
            selected.extend(pool[:cap])
    return selected


# 히어로 장소들의 상위 매칭 곡은 반드시 재생 가능해야 한다 (시연 안전, AGENTS.md §2).
HERO_PLACE_IDS = ["gyeongbokgung", "hahoe", "jeonju_hanok", "namdaemun"]
HERO_TOP_N = 8


def _hero_required(all_tracks: list[dict]) -> list[dict]:
    """히어로 장소별 상위 매칭 트랙을 다운로드 대상에 강제 포함 (top-5 가 항상 5/5 재생되도록)."""
    try:
        sys.path.insert(0, os.path.dirname(_PREP_DIR))  # backend/
        from embeddings import load_places, load_tracks
        from matching import match
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] 히어로 보장 건너뜀(매칭 모듈 로드 실패): {exc}")
        return []
    places, tracks = load_places(), load_tracks()
    req: set[str] = set()
    for pid in HERO_PLACE_IDS:
        p = next((x for x in places if x["id"] == pid), None)
        if p:
            for t in match(p, tracks)[:HERO_TOP_N]:
                req.add(t["id"])
    return [t for t in all_tracks if t["id"] in req]


def _group_by_region(tracks: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for t in tracks:
        out[t.get("region", "")].append(t)
    return out


def main() -> None:
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    all_tracks = _load_tracks()
    tracks = _select_for_download(all_tracks)
    # 히어로 장소 상위 매칭곡을 union (중복 id 제외) → 시연 경로 100% 재생 보장
    seen_ids = {t["id"] for t in tracks}
    for t in _hero_required(all_tracks):
        if t["id"] not in seen_ids:
            tracks.append(t)
            seen_ids.add(t["id"])

    ok, skip, fail = 0, 0, 0
    for t in tracks:
        url = t.get("audio_source_url")
        rel = t.get("audio_path", "")               # "/audio/igbf_xxx.wav"
        if not url or not rel:
            continue
        out_path = os.path.join(_AUDIO_DIR, os.path.basename(rel))
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            skip += 1
            continue
        try:
            # 소스가 WAV(민요·국립국악원 샘플)면 30초 클립을 받아 MP3 로 변환(용량 절감),
            # 소스가 MP3(공유마당 정악·BGM)면 그대로 받는다. 타깃 audio_path 는 항상 .mp3.
            if url.lower().endswith(".wav"):
                fetch_wav_as_mp3(url, out_path)
            else:
                download_full(url, out_path)
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"  ✓ {t['id']:18} {size_mb:4.1f}MB  {t['title']}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {t['id']:18} 실패: {type(exc).__name__}: {exc}")
            fail += 1

    print(f"\n완료: 신규 {ok} · 건너뜀(이미 있음) {skip} · 실패 {fail} / 총 {len(tracks)}곡")


if __name__ == "__main__":
    main()
