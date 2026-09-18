"""确定性哈希向量，可替换为 BGE-M3。"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable


class HashEmbedder:
    def __init__(self, dim: int = 64, model: str = "hash-v1") -> None:
        self.dim = dim
        self.model = model

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = list(text or "")
        for i, ch in enumerate(tokens):
            digest = hashlib.sha256(f"{ch}:{i}".encode("utf-8")).digest()
            idx = digest[0] % self.dim
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
