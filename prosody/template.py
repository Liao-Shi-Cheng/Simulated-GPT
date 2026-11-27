"""句式 → 格式推导。

四个五言基本句式（P=平，Z=仄）：

======  =======  ====  ====  ======
句式    平仄     起式  句末  是否韵句
======  =======  ====  ====  ======
A       ZZPPZ    仄起  仄    否
B       PPZZP    平起  平    是
C       PPPZZ    平起  仄    否
D       ZZZPP    仄起  平    是
======  =======  ====  ====  ======

格式**不手工写死**，只从首句句式推：偶数句（1、3）必押韵（平收），
奇数句（2）仄收；联内上下句"对"，联间"粘"。

一个容易写错的点：工作说明 §3.3.2 概括"对 = A↔B、C↔D"，但按它推
B 起会得到 BADC，与 §3.3.2 表格里的 BDAB 不符。原因是"一三五不论"——
**对**只约束第 2、4 字（0-indexed 的 1、3），不是整句五字取反；按 2/4 字
取反并结合"偶数句押韵"筛选，才能唯一推出表格中的四个格式。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PATTERNS_PATH = Path(__file__).resolve().parent / "data" / "patterns.json"

#: 句数。五绝是主战场；五律只是把同一条对/粘规则往后推两联，
#: 用来在真实唐诗上验证判定器（不做对仗判定，见工作说明 §1.4）。
FORMS: dict[str, int] = {"五绝": 4, "五律": 8}


@dataclass(frozen=True)
class Template:
    form: str                    # "五绝"
    first: str                   # "A" | "B" | "C" | "D"
    lines: tuple[str, ...]       # ("ZZPPZ", "PPZZP", "PPPZZ", "ZZZPP")
    rhyme_lines: tuple[int, ...] # 0-indexed，如 (1, 3)


@lru_cache(maxsize=1)
def patterns() -> dict[str, str]:
    """句式名 → 平仄串。"""
    payload = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    return {name: item["pz"] for name, item in payload["patterns"].items()}


@lru_cache(maxsize=1)
def pattern_info() -> dict[str, dict]:
    """句式名 → {"pz", "start", "rhyme", "reading"}。"""
    payload = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    return {name: dict(item) for name, item in payload["patterns"].items()}


@lru_cache(maxsize=1)
def variants() -> dict[str, dict]:
    """变体句式：键为变体名（"teao" / "gujiu"）。"""
    payload = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    return {name: dict(item) for name, item in payload.get("variants", {}).items()}


def _dui_candidates(prev: str) -> list[str]:
    """联内上下句相"对"：第 2、4 字平仄相反。"""
    p = patterns()[prev]
    return [k for k, v in patterns().items() if v[1] != p[1] and v[3] != p[3]]


def _nian_candidates(prev: str) -> list[str]:
    """联间相"粘"：本句第 2 字与上联下句第 2 字平仄相同。"""
    p = patterns()[prev]
    return [k for k, v in patterns().items() if v[1] == p[1]]


def _pick(cands: list[str], want_rhyme: bool, what: str) -> str:
    # 偶数句押平声韵（句末 P），奇数句仄收（句末 Z），据此在候选里消歧。
    filtered = [k for k in cands if (patterns()[k][-1] == "P") == want_rhyme]
    if len(filtered) != 1:
        raise ValueError(f"{what} 推导不唯一: 候选 {cands} → {filtered}")
    return filtered[0]


def build_template(first: str, form: str = "五绝") -> Template:
    """由首句句式推出整首格式。"""
    if form not in FORMS:
        raise ValueError(f"暂不支持的形式: {form!r}（可选 {list(FORMS)}）")
    first = first.strip().upper()
    if first not in patterns():
        raise ValueError(f"未知首句句式: {first!r}（可选 {list(patterns())}）")

    lines: list[str] = [first]
    for i in range(1, FORMS[form]):
        if i % 2 == 1:      # 每联的下句：与上句相对，且押韵
            lines.append(_pick(_dui_candidates(lines[-1]), True, f"第{i + 1}句"))
        else:               # 每联的上句：与上联下句相粘，且不押韵
            lines.append(_pick(_nian_candidates(lines[-1]), False, f"第{i + 1}句"))
    rhyme_lines = tuple(i for i, line in enumerate(lines) if patterns()[line][-1] == "P")
    # 首句入韵与否必须由首句句式唯一决定，不是自由参数（§3.3.2）。
    if (0 in rhyme_lines) != (patterns()[first][-1] == "P"):
        raise AssertionError("首句入韵判定与句式不一致")
    return Template(
        form=form,
        first=first,
        lines=tuple(patterns()[line] for line in lines),
        rhyme_lines=rhyme_lines,
    )


def all_templates(form: str = "五绝") -> list[Template]:
    """四个首句句式对应的全部格式，顺序固定为 A、B、C、D。"""
    return [build_template(first, form) for first in ("A", "B", "C", "D")]
