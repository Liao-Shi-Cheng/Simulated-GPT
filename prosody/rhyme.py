"""韵部查询：韵脚用平声韵，一韵到底。

``rhyme_group`` 只回答平声韵部：近体诗押平声韵，仄声字不能做韵脚，
所以查韵脚时平声韵部才有意义；仄声韵部留给 ``chars_in_group`` / 校验用。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .pingze import PING, char_groups, group_names, group_info

FREQ_PATH = Path(__file__).resolve().parent / "data" / "rhyme_freq.json"


@lru_cache(maxsize=1)
def _all_groups() -> dict[str, frozenset[str]]:
    return {name: frozenset(group_info(name)["chars"]) for name in group_names()}


@lru_cache(maxsize=1)
def _ping_groups() -> dict[str, frozenset[str]]:
    return {name: chars for name, chars in _all_groups().items() if group_info(name)["tone"] == PING}


def _normalize(name: str) -> str:
    """允许 "上平声一东" / "一东" 两种写法。"""
    n = name.strip()
    for prefix in ("上平声", "下平声", "平声", "上声", "去声", "入声"):
        if n.startswith(prefix) and n[len(prefix):] in _all_groups():
            return n[len(prefix):]
    return n


def rhyme_groups(ch: str) -> tuple[str, ...]:
    """该字可用的**平声**韵部，按韵书顺序；非平声或未收录返回空元组。

    一个平声字可能兼属两个平声韵部（如 逢 在 一东 / 三江），韵脚只要落在
    其中一个即可，所以判定时要用集合求交，不能只取第一个。
    """
    return tuple(g for g in char_groups(ch) if group_info(g)["tone"] == PING)


def rhyme_group(ch: str) -> str | None:
    """返回韵部名（如 "一东"）；非平声或未收录返回 None。

    兼属多个平声韵部时返回韵书顺序里的第一个，要完整集合请用 ``rhyme_groups``。
    """
    groups = rhyme_groups(ch)
    return groups[0] if groups else None


def chars_in_group(group: str) -> frozenset[str]:
    """韵部内的字集合（106 个韵部通用，含仄声韵部）。"""
    key = _normalize(group)
    try:
        return _all_groups()[key]
    except KeyError:
        raise KeyError(f"未知韵部: {group!r}") from None


def top_groups(k: int = 10) -> list[str]:
    """语料中最高频的 k 个平声韵部。

    频率来自 ``prepare.py`` 统计出的 ``data/rhyme_freq.json``；文件缺失时退化为
    韵书顺序（此时只是"前 k 个韵部"，不代表高频，实验前请先跑一遍 prepare）。
    """
    if k <= 0:
        return []
    ping_names = list(_ping_groups())
    counts = _freq_counts()
    if not counts:
        return ping_names[:k]
    order = {name: i for i, name in enumerate(ping_names)}
    ranked = sorted(
        (name for name in ping_names),
        key=lambda n: (-counts.get(n, 0), order[n]),
    )
    return ranked[:k]


@lru_cache(maxsize=1)
def _freq_counts() -> dict[str, int]:
    if not FREQ_PATH.exists():
        return {}
    payload = json.loads(FREQ_PATH.read_text(encoding="utf-8"))
    counts = payload.get("rhyme_groups", {})
    return {k: int(v) for k, v in counts.items() if k in _all_groups()}
