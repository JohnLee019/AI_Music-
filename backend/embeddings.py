"""임베딩 로드 및 코사인 유사도 계산 (numpy only, 런타임 ML 모델 없음)."""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_json(filename: str) -> list[dict[str, Any]]:
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도 [-1, 1]."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def load_places() -> list[dict[str, Any]]:
    return _load_json("places.json")


def load_tracks() -> list[dict[str, Any]]:
    return _load_json("tracks.json")


def load_reasoning() -> dict[str, str]:
    """사전 생성된 근거 텍스트 로드. 파일이 없거나 손상돼도 데모는 멈추지 않는다
    (main.py 가 메타데이터 템플릿 근거로 폴백한다 — AGENTS.md §2)."""
    path = os.path.join(DATA_DIR, "reasoning.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
