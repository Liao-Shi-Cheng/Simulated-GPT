"""平水韵表加载与平仄查询。

约定（全项目统一）：

- ``"P"`` = 平声，``"Z"`` = 仄声，``"PZ"`` = 该字平仄两读（多音字 / 兼韵）。
- 入声字在普通话里可以读阴平、阳平，但中古音属仄声。因此**禁止**用
  ``pypinyin`` 之类的现代读音判平仄，只能查本模块的平水韵表。
- 平声 = 上平声 + 下平声共 30 韵部；仄声 = 上声 / 去声 / 入声共 76 韵部。

数据来源见 ``data/build_pingshui.py``。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .variants import normalize

PING = "P"
ZE = "Z"
BOTH = "PZ"

DATA_PATH = Path(__file__).resolve().parent / "data" / "pingshui.json"


def is_cjk(ch: str) -> bool:
    """是否为单个汉字：基本区 + 扩展 A/B 区（韵表里有少量扩展区字）。"""
    if len(ch) != 1:
        return False
    o = ord(ch)
    return 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF or 0x20000 <= o <= 0x2FFFF


@lru_cache(maxsize=1)
def _raw_groups() -> dict[str, dict]:
    """韵部名 → {"tone", "category", "num", "section", "chars"}，保持韵书顺序。"""
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {g["name"]: g for g in payload["groups"]}


@lru_cache(maxsize=1)
def _char_index() -> dict[str, tuple[str, tuple[str, ...]]]:
    """字 → (平仄, 所属韵部名元组)。韵部按韵书顺序排列，平仄为所有读音的并集。"""
    tones: dict[str, set[str]] = {}
    groups: dict[str, list[str]] = {}
    for name, info in _raw_groups().items():
        for ch in info["chars"]:
            tones.setdefault(ch, set()).add(info["tone"])
            groups.setdefault(ch, []).append(name)
    index: dict[str, tuple[str, tuple[str, ...]]] = {}
    for ch, ts in tones.items():
        tone = PING if ts == {PING} else ZE if ts == {ZE} else BOTH
        index[ch] = (tone, tuple(dict.fromkeys(groups[ch])))
    return index


def load_pingshuiyun() -> dict[str, str]:
    """返回 字 → 平仄 的 dict（"P" / "Z" / "PZ"）。"""
    return {ch: tone for ch, (tone, _) in _char_index().items()}


def char_pingze(ch: str) -> str | None:
    """查询单字的平仄：``"P"`` / ``"Z"`` / ``"PZ"``；非汉字或未收录返回 ``None``。

    查不到的字**不等于**平声，调用方必须显式处理 ``None``（例如判为不合律）。
    """
    if not is_cjk(ch):
        return None
    entry = _lookup(ch)
    return entry[0] if entry else None


def char_groups(ch: str) -> tuple[str, ...]:
    """该字所属的全部韵部（平仄都有，按韵书顺序）；未收录返回空元组。"""
    if not is_cjk(ch):
        return ()
    entry = _lookup(ch)
    return entry[1] if entry else ()


def _lookup(ch: str) -> tuple[str, tuple[str, ...]] | None:
    """先查本字，查不到再按异体字归一化后查一次。"""
    entry = _char_index().get(ch)
    if entry is None:
        alt = normalize(ch)
        if alt != ch:
            entry = _char_index().get(alt)
    return entry


def group_info(name: str) -> dict:
    """韵部信息（返回副本，避免调用方改到缓存）。"""
    info = _raw_groups().get(name)
    if info is None:
        raise KeyError(f"未知韵部: {name!r}")
    return dict(info)


def group_names(tone: str | None = None) -> tuple[str, ...]:
    """全部韵部名；``tone="P"`` 只取 30 个平声韵部。"""
    names = tuple(_raw_groups())
    if tone is None:
        return names
    return tuple(n for n in names if _raw_groups()[n]["tone"] == tone)


def matches(actual: str | None, want: str) -> bool:
    """``actual``（``char_pingze`` 的返回值）能否满足模板要求的 ``want``。

    ``"PZ"`` 视为两种读法都有，所以模板要 P 要 Z 都算合格——这是多音字在
    格律判定里的既有做法；真正的取舍留给解码期按上下文决定。
    """
    return actual is not None and actual != "" and want in actual
