"""数据预处理入口：原始 JSON → train/val/test.bin + meta.json + stats.json。

用法：
    python prepare.py --raw data/raw --out data/processed

流程（对应工作说明 §3.2）：
    1. 读原始 JSON，按作品聚合成完整文本
    2. 繁转简（opencc）+ 异体字归一
    3. 两级去重：完全重复、去标点后重复
    4. 按作品随机切分 90/5/5（固定 seed）
    5. 建字表，出现次数 < min_freq 的映射到 <unk>
    6. 编码为 uint16 写入 .bin

顺带产出两样东西：
    - data/processed/stats.json：数据统计（字频、句长、五绝格式分布、合律率、韵部频率）
    - prosody/data/rhyme_freq.json：语料中的平声韵部频率，供 prosody.rhyme.top_groups 使用

注意：标点保留（模型要学断句），空行/换行也是 token；不按行切分，按作品切分。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import opencc

from prosody.check import check
from prosody.pingze import BOTH, PING, ZE, char_pingze, is_cjk
from prosody.rhyme import rhyme_groups
from prosody.template import all_templates
from prosody.variants import normalize_text

# 只保留这些标点 + 换行：语料里的括号注、书名号里常混入说明文字，宁缺勿滥
KEEP_PUNCT = set("，。、；：？！…—“”‘’（）《》〈〉「」『』【】,.;:?!·")
SEP = "\n"
# 原始 JSON 的 paragraphs 是"联"（两句用逗号连写），拆句要按标点切
SENT_RE = re.compile("[" + re.escape("".join(KEEP_PUNCT)) + "]")
UNK = "<unk>"


@dataclass
class Poem:
    lines: list[str]                      # 含标点的一行一句
    clean: str                            # 只含汉字，用于去重与统计
    text: str = ""
    title: str = ""
    author: str = ""

    def __post_init__(self) -> None:
        self.text = SEP.join(self.lines)


@dataclass
class Stats:
    raw_poems: int = 0
    dropped_short: int = 0
    exact_dup: int = 0
    near_dup: int = 0
    poems: list[Poem] = field(default_factory=list)


def iter_raw(raw_dir: Path):
    """遍历原始 JSON。每个文件是一个 list，元素带 paragraphs 字段。"""
    for path in sorted(raw_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:               # 坏文件不该拖垮整个流程
            print(f"!! 跳过 {path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if isinstance(item, dict) and item.get("paragraphs"):
                yield item


def normalize_poem(item: dict, conv: opencc.OpenCC, min_chars: int = 10) -> Poem | None:
    """单首归一化：繁转简 → 异体字归一 → 去掉不认识的字符。"""
    lines: list[str] = []
    for para in item["paragraphs"]:
        s = normalize_text(conv.convert(para))
        s = "".join(ch for ch in s if is_cjk(ch) or ch in KEEP_PUNCT).strip()
        if s:
            lines.append(s)
    clean = "".join(ch for ch in "".join(lines) if is_cjk(ch))
    if len(clean) < min_chars:
        return None
    return Poem(lines=lines, clean=clean,
                title=str(item.get("title", "")), author=str(item.get("author", "")))


def collect(raw_dir: Path, min_chars: int = 10) -> Stats:
    """读目录 + 两级去重。"""
    conv = opencc.OpenCC("t2s.json")
    stats = Stats()
    seen_text: set[str] = set()
    seen_clean: set[str] = set()
    for item in iter_raw(raw_dir):
        stats.raw_poems += 1
        poem = normalize_poem(item, conv, min_chars)
        if poem is None:
            stats.dropped_short += 1
            continue
        if poem.text in seen_text:
            stats.exact_dup += 1
            continue
        if poem.clean in seen_clean:        # 去标点后相同 = 近似重复
            stats.near_dup += 1
            continue
        seen_text.add(poem.text)
        seen_clean.add(poem.clean)
        stats.poems.append(poem)
    return stats


def split_poems(poems: list[Poem], seed: int, ratios=(0.90, 0.05, 0.05)) -> dict[str, list[Poem]]:
    """按作品切分（绝不按行）。"""
    order = list(range(len(poems)))
    random.Random(seed).shuffle(order)
    n = len(order)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    idx = {
        "train": order[:n_train],
        "val": order[n_train:n_train + n_val],
        "test": order[n_train + n_val:],
    }
    return {k: [poems[i] for i in v] for k, v in idx.items()}


def build_vocab(poems: list[Poem], min_freq: int) -> list[str]:
    """字表：``<unk>`` 固定 0、换行固定 1，其余按频次降序，同频按码位（可复现）。

    换行必须无条件入表：它是作品分隔符，缺了就会全部落到 ``<unk>``。
    """
    cnt = Counter()
    for p in poems:
        cnt.update(p.text)
    kept = [(ch, c) for ch, c in cnt.items()
            if c >= min_freq and ch not in (UNK, SEP)]
    kept.sort(key=lambda x: (-x[1], ord(x[0])))
    return [UNK, SEP] + [ch for ch, _ in kept]


def encode(poems: list[Poem], itos: list[str]) -> np.ndarray:
    stoi = {ch: i for i, ch in enumerate(itos)}
    unk = stoi[UNK]
    ids: list[int] = []
    for p in poems:
        ids.extend(stoi.get(ch, unk) for ch in p.text)
        ids.append(stoi.get(SEP, unk))
    if not ids:
        raise ValueError("语料为空")
    arr = np.asarray(ids, dtype=np.uint16)
    if arr.max() >= stoi.get(UNK, 0) + len(itos):
        raise AssertionError("token id 越界")
    return arr


def sentences(poem: Poem) -> list[str]:
    """按标点拆句（原始 paragraphs 是"联"，一句一联地拆开）。"""
    out: list[str] = []
    for line in poem.lines:
        out.extend(part for part in SENT_RE.split(line) if part.strip())
    return out


def poem_form(poem: Poem) -> tuple[str | None, list[str]]:
    """五绝判定：4 句 × 5 字，返回匹配的首句句式与四句汉字。"""
    rows = ["".join(ch for ch in s if is_cjk(ch)) for s in sentences(poem)]
    if len(rows) != 4 or any(len(r) != 5 for r in rows):
        return None, rows
    for t in all_templates():
        if check(SEP.join(rows), t, strict=False, allow_teao=True).ok:
            return t.first, rows
    return None, rows


def compute_stats(poems: list[Poem], itos: list[str],
                  splits: dict[str, list[Poem]]) -> tuple[dict, Counter]:
    counts = Counter()
    for p in poems:
        counts.update(ch for ch in p.text if is_cjk(ch))
    tones = Counter()
    unknown: Counter[str] = Counter()
    for ch, c in counts.items():
        pz = char_pingze(ch)
        if pz is None:
            unknown[ch] += c
        else:
            tones[pz] += c

    line_lens = Counter(len("".join(ch for ch in s if is_cjk(ch)))
                        for p in poems for s in sentences(p))

    # 五绝：格式分布、合律率、韵部频率
    form = Counter()
    rhyme = Counter()
    first_rhyme = Counter()
    five_jue = 0
    rhyme_kind = Counter()
    for p in poems:
        first, rows = poem_form(p)
        # 只统计"4 句 × 5 字"的作品；4 句七言不是五绝
        if len(rows) != 4 or any(len(r) != 5 for r in rows):
            continue
        five_jue += 1
        # 判失败前先看韵脚：仄韵（第 2、4 句都仄收）的多是古绝，不是"判定错"
        feet = [char_pingze(rows[i][-1]) for i in (1, 3)]
        if all(f == ZE for f in feet):
            rhyme_kind["仄韵"] += 1
        elif all(f == PING for f in feet):
            rhyme_kind["平韵"] += 1
        else:
            rhyme_kind["混/缺"] += 1
        if first is None:
            form["未匹配"] += 1
            continue
        form[first] += 1
        t = next(t for t in all_templates() if t.first == first)
        first_rhyme["首句入韵" if 0 in t.rhyme_lines else "首句不入韵"] += 1
        feet = [rows[i][-1] for i in t.rhyme_lines]
        common = None
        for ch in feet:
            gs = set(rhyme_groups(ch))
            common = gs if common is None else common & gs
        for g in sorted(common or ()):
            rhyme[g] += 1

    total = sum(counts.values())
    return {
        "poems": len(poems),
        "chars": total,
        "vocab_size": len(itos),
        "version": "1.0",
        "splits": {k: {"poems": len(v), "chars": int(sum(len(p.text) for p in v))}
                   for k, v in splits.items()},
        "lines": {"count": sum(line_lens.values())},
        "line_length": dict(sorted(line_lens.items())),
        "tones": {"P": tones[PING], "Z": tones[ZE], "PZ": tones[BOTH], "缺失": sum(unknown.values())},
        "unknown_chars": {"types": len(unknown), "occurrences": sum(unknown.values()),
                          "top": unknown.most_common(50)},
        "top_chars": counts.most_common(50),
        "five_jue": {"total": five_jue, "valid": five_jue - form["未匹配"],
                     "rate": round((five_jue - form["未匹配"]) / five_jue, 4) if five_jue else None,
                     "forms": dict(form), "first_rhyme": dict(first_rhyme),
                     "rhyme_kind": dict(rhyme_kind)},
        "unknown_rate": round(sum(unknown.values()) / total, 6) if total else None,
    }, rhyme


def write_freq(rhyme: dict, path: Path) -> None:
    path.write_text(json.dumps({
        "meta": {"what": "全唐诗中五绝韵脚的平声韵部频率",
                 "generated_by": "prepare.py"},
        "rhyme_groups": dict(rhyme.most_common()),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="数据预处理")
    parser.add_argument("--raw", default="data/raw", help="原始语料目录")
    parser.add_argument("--out", default="data/processed", help="输出目录")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--min-freq", type=int, default=3, help="低于该频次的字映射到 <unk>")
    parser.add_argument("--min-chars", type=int, default=10, help="整首少于该字数直接丢弃")
    parser.add_argument("--no-freq", action="store_true", help="不写 rhyme_freq.json")
    args = parser.parse_args()

    raw_dir, out_dir = Path(args.raw), Path(args.out)
    if not raw_dir.is_dir():
        print(f"!! 原始语料目录不存在: {raw_dir}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = collect(raw_dir, args.min_chars)
    if not stats.poems:
        print("!! 没有读到任何作品，检查 --raw 是否指向含 paragraphs 的 JSON", file=sys.stderr)
        return 1
    split = split_poems(stats.poems, args.seed)
    itos = build_vocab(stats.poems, args.min_freq)

    for name, poems in split.items():
        arr = encode(poems, itos)
        arr.tofile(out_dir / f"{name}.bin")
        print(f"{name}.bin: {len(poems)} 首 / {arr.size} tokens", file=sys.stderr)

    meta = {
        "vocab_size": len(itos),
        "itos": itos,
        "seed": args.seed,
        "min_freq": args.min_freq,
        "min_chars": args.min_chars,
        "unk_id": 0,
        "counts": {
            "raw_poems": stats.raw_poems,
            "kept_poems": len(stats.poems),
            "dropped_short": stats.dropped_short,
            "exact_dup": stats.exact_dup,
            "near_dup": stats.near_dup,
        },
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    doc_stats, rhyme = compute_stats(stats.poems, itos, split)
    (out_dir / "stats.json").write_text(
        json.dumps(doc_stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if not args.no_freq:
        freq_path = Path(__file__).resolve().parent / "prosody" / "data" / "rhyme_freq.json"
        write_freq(rhyme, freq_path)
        print(f"韵部频率 → {freq_path}", file=sys.stderr)

    print(
        f"作品 {doc_stats['poems']}，字符 {doc_stats['chars']}，词表 {len(itos)}，"
        f"未知字占比 {doc_stats['unknown_rate']:.4%}，"
        f"五绝 {doc_stats['five_jue']['total']} 首、合律率 {doc_stats['five_jue']['rate']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
