"""异体字归一化：把 疎/劒/猨 这类字收敛到韵表里的通行字。

唐诗语料里约 1% 的字次是异体字，opencc 的 t2s 不处理它们（那本来就不是
繁简问题）。不归一化的话：语料词表会多出上千个同字异形，格律判定会把
它们判成"未收录"。

映射表由 ``data/build_variants.py`` 生成，映射目标一定能在平水韵表里查到。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

VARIANTS_PATH = Path(__file__).resolve().parent / "data" / "variants.json"


@lru_cache(maxsize=1)
def _map() -> dict[str, str]:
    if not VARIANTS_PATH.exists():      # 表缺失时退化为"不归一化"，不阻断流程
        return {}
    payload = json.loads(VARIANTS_PATH.read_text(encoding="utf-8"))
    return payload.get("map", {})


def normalize(ch: str) -> str:
    """单个字归一化；无映射原样返回。"""
    return _map().get(ch, ch)


def normalize_text(text: str) -> str:
    """逐字归一化（不做词级替换，保持字符一一对应，便于回查）。"""
    table = _map()
    return "".join(table.get(ch, ch) for ch in text)
