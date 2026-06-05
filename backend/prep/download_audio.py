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
import urllib.request

_PREP_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_PREP_DIR, "..", "..", "data")
_AUDIO_DIR = os.path.join(_DATA_DIR, "audio")
_TRACKS_JSON = os.path.join(_DATA_DIR, "tracks.json")

TRIM_SECONDS = 30
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
    """압축 오디오(mp3 등)를 그대로 내려받는다 (트림 불가, ffmpeg 없이)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if not data:
        raise RuntimeError("빈 응답 (다운로드 불가)")
    with open(out_path, "wb") as f:
        f.write(data)


def _load_tracks() -> list[dict]:
    with open(_TRACKS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data["tracks"] if isinstance(data, dict) else data


def main() -> None:
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    tracks = _load_tracks()

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
            # wav 는 30초 트림(Range), 그 외(mp3 등)는 압축이라 전체 다운로드.
            if rel.lower().endswith(".wav"):
                trim_remote_wav(url, out_path)
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
