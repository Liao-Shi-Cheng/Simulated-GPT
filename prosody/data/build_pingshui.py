"""由两份原始韵表生成 pingshui.json（简体 + 交叉核对）。

运行：python prosody/data/build_pingshui.py

为什么要有这一步：

- ``RAW.json`` 是主表（繁体），需要 opencc 转简体才能和语料/生成结果对齐；
- 单表不可信（工作说明 §5.2 把"平水韵表"列为 B 的最大风险），所以用
  ``RAW2.json``（另一来源的公开表）交叉核对：共享字平仄分歧记入
  ``pingshui_conflicts.json``，供人工抽查；``RAW2`` 独有的字补进主表，
  主表独有的字保持原样（主表优先）。
- 两张表都是脏数据：``RAW.json`` 末组混入了 "Publicdomain..." 字样，
  ``RAW2.json`` 带 ``[刨，挖]`` 这类注文，统一按"只保留汉字"过滤，重复导入幂等。

字段约定见 ``prosody/pingze.py``。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import opencc

HERE = Path(__file__).resolve().parent
RAW = HERE / "RAW.json"          # 主表（繁体）
RAW2 = HERE / "RAW2.json"        # 交叉核对表（简体，带注文）
OUT = HERE / "pingshui.json"
CONFLICTS = HERE / "pingshui_conflicts.json"

# 韵部一级分类 → (平仄, 规范类名)。入声在普通话里读平/上/去，但中古音属仄，
# 这是整个项目不能用 pypinyin 的原因（工作说明 §3.3.4）。
TONE_OF_SECTION = {
    "上平聲部": ("P", "上平声"),
    "下平聲部": ("P", "下平声"),
    "上聲部": ("Z", "上声"),
    "去聲部": ("Z", "去声"),
    "入聲部": ("Z", "入声"),
}

# RAW.json 的结构是 {"ping": {"上平聲部": …}, "ze": {…}}，
# 按韵书顺序展平，section 序号即规范顺序。
SECTION_PLAN = [
    ("ping", "上平聲部"),
    ("ping", "下平聲部"),
    ("ze", "上聲部"),
    ("ze", "去聲部"),
    ("ze", "入聲部"),
]

HEAD_RE = re.compile(r"^(上平聲|下平聲|上聲|去聲|入聲)([一二三四五六七八九十]+)(.+)$")
TAIL_RE = re.compile(r"^(.+?)(平|上|去|入)$")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ffff]+")

CHINESE_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17,
    "十八": 18, "十九": 19, "二十": 20, "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24,
    "二十五": 25, "二十六": 26, "二十七": 27, "二十八": 28, "二十九": 29, "三十": 30,
}

# 两表对同一韵部的不同写法（韵名用字不同），对齐到主表写法。
RHYME_ALIAS = {"十七筱": "十七筿", "二十八俭": "二十八琰"}

AUX_TONE = {"平": "P", "上": "Z", "去": "Z", "入": "Z"}

# 主表漏收的补正（人工核对）。只收"能拿出证据"的：
# 先/槎 在唐代都是常用平声韵脚，主表却只把它们收在仄声韵部，直接用会误判。
GAP_FIX = {
    "先": ("一先", "主表只收进 十七霰（去声），漏了平声本义；刘长卿《新年作》'春归在客先'押先韵"),
    "槎": ("六麻", "主表只收进 上声二十一马；唐诗'星槎/灵槎'多押麻韵平声"),
}


def clean_chars(text: str) -> str:
    """只保留汉字，去重并按出现顺序排列。"""
    return "".join(dict.fromkeys("".join(CJK_RE.findall(text))))


def split_name(raw_name: str) -> tuple[str, str]:
    """'上平聲十五刪' → ('上平聲', '十五刪')。"""
    m = HEAD_RE.match(raw_name.strip())
    if not m:
        raise ValueError(f"无法解析韵部名: {raw_name!r}")
    head, num, _ = m.groups()
    if num not in CHINESE_NUM:
        raise ValueError(f"未知序号: {raw_name!r}")
    return head, num


def load_primary(conv: opencc.OpenCC) -> list[dict]:
    """主表：繁体 → 简体，逐字转换（整串转换会被 opencc 按词组处理而改错字）。"""
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    groups: list[dict] = []
    seen: set[str] = set()
    for section_idx, (parent, section) in enumerate(SECTION_PLAN):
        tone, category = TONE_OF_SECTION[section]
        for raw_name, lines in raw[parent][section].items():
            head, num = split_name(raw_name)
            if head + "部" != section:
                raise ValueError(f"{raw_name!r} 出现在错误的分类下")
            chars = "".join(conv.convert(ch) for ch in clean_chars(lines[0]))
            # 不同繁体字可能转成同一个简体字（冬/鼕 → 冬），转换后要再去重
            chars = "".join(dict.fromkeys(chars))
            name = num + conv.convert(raw_name[len(head) + len(num):])
            if name in seen:
                raise ValueError(f"韵部重名: {name}")
            seen.add(name)
            groups.append(
                {
                    "name": name,
                    "tone": tone,
                    "category": category,
                    "num": CHINESE_NUM[num],
                    "section": section_idx,
                    "chars": chars,
                }
            )
    return groups


def load_aux(groups: list[dict]) -> dict[str, str]:
    """交叉核对表：韵部名 → 字串。韵名用字差异按 RHYME_ALIAS 对齐。"""
    raw = json.loads(RAW2.read_text(encoding="utf-8"))
    known = {g["name"] for g in groups}
    out: dict[str, str] = {}
    for raw_name, text in raw.items():
        m = TAIL_RE.match(raw_name.replace("\ufeff", "").strip())
        if not m:
            raise ValueError(f"无法解析韵部名: {raw_name!r}")
        name = RHYME_ALIAS.get(m.group(1), m.group(1))
        if name not in known:
            raise ValueError(f"交叉核对表出现未知韵部: {name!r}（原始 {raw_name!r}）")
        if AUX_TONE[m.group(2)] != next(g["tone"] for g in groups if g["name"] == name):
            raise ValueError(f"两表对 {name} 的平仄归类不一致")
        out[name] = clean_chars(text)
    missing = known - set(out)
    if missing:
        raise ValueError(f"交叉核对表缺韵部: {sorted(missing)}")
    return out


def corpus_charset(corpus_dir: Path, conv: opencc.OpenCC) -> set[str]:
    """语料中实际出现过的汉字（繁转简后）。"""
    chars: set[str] = set()
    for path in sorted(corpus_dir.glob("*.json")):
        for poem in json.loads(path.read_text(encoding="utf-8")):
            for line in poem.get("paragraphs", []):
                chars.update(ch for ch in conv.convert(line) if CJK_RE.match(ch))
    return chars


def merge(groups: list[dict], aux: dict[str, str], attested: set[str], aux_filter: bool) -> dict:
    primary_chars: dict[str, str] = {}
    for g in groups:
        for ch in g["chars"]:
            primary_chars.setdefault(ch, g["tone"])

    added = 0
    for g in groups:
        extra = [
            ch for ch in aux[g["name"]]
            if ch not in primary_chars and (ch in attested or not aux_filter)
        ]
        added += len(extra)
        g["chars"] = g["chars"] + "".join(extra)

    # 主表漏收的补正：字可能已在别的韵部里，但这一部漏了
    by_name = {g["name"]: g for g in groups}
    fixed = []
    for ch, (group, why) in GAP_FIX.items():
        if group not in by_name:
            raise KeyError(f"补正指向未知韵部: {group}")
        if ch not in by_name[group]["chars"]:
            by_name[group]["chars"] += ch
            fixed.append({"char": ch, "group": group, "why": why})

    # 冲突：共享字在两表里平仄不同。主表优先，冲突表留给人工抽查。
    aux_tone: dict[str, set[str]] = {}
    for name, chars in aux.items():
        tone = next(g["tone"] for g in groups if g["name"] == name)
        for ch in chars:
            aux_tone.setdefault(ch, set()).add(tone)
    conflicts = {
        ch: {"primary": t, "aux": "".join(sorted(aux_tone[ch]))}
        for ch, t in primary_chars.items()
        if aux_tone.get(ch) and aux_tone[ch] != {t}
    }
    return {"added": added, "conflicts": conflicts, "gap_fix": fixed}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 pingshui.json")
    parser.add_argument("--corpus", default=str(HERE.parents[1] / "data" / "raw" / "tang"),
                        help="语料目录，用于只收真实出现过的补字")
    parser.add_argument("--all-aux", action="store_true",
                        help="不按语料过滤，把交叉表的字全部并入（会引入大量生僻字）")
    args = parser.parse_args()

    conv = opencc.OpenCC("t2s.json")
    groups = load_primary(conv)
    aux = load_aux(groups)

    attested: set[str] = set()
    if args.all_aux:
        aux_filter = False
        print("!! --all-aux：交叉表补字不做语料过滤，韵部字表会明显膨胀", file=sys.stderr)
    else:
        corpus_dir = Path(args.corpus)
        if not corpus_dir.is_dir():
            aux_filter = False
            print(f"!! 找不到语料目录 {corpus_dir}，跳过补字；"
                  f"需要补字请先下载语料或用 --all-aux", file=sys.stderr)
        else:
            aux_filter = True
            attested = corpus_charset(corpus_dir, conv)
            print(f"语料字种 {len(attested)}", file=sys.stderr)

    report = merge(groups, aux, attested, aux_filter)

    per_char: dict[str, set[str]] = {}
    for g in groups:
        for ch in g["chars"]:
            per_char.setdefault(ch, set()).add(g["tone"])
    mixed = sum(1 for ts in per_char.values() if len(ts) > 1)

    out = {
        "meta": {
            "name": "平水韵",
            "version": "1.1",
            "source": "主表 RAW.json（繁体，opencc t2s 转简）；交叉核对 RAW2.json",
            "generated_by": "prosody/data/build_pingshui.py",
            "counts": {
                "groups": len(groups),
                "ping_groups": sum(g["tone"] == "P" for g in groups),
                "ze_groups": sum(g["tone"] == "Z" for g in groups),
                "chars": len(per_char),
                "entries": sum(len(g["chars"]) for g in groups),
                "polyphone": mixed,
                "aux_added": report["added"],
                "gap_fixed": len(report["gap_fix"]),
                "conflicts": len(report["conflicts"]),
                "gap_fix": report["gap_fix"],
            },
            "notes": [
                "平声 = 上平声 + 下平声共 30 部；仄声 = 上/去/入声共 76 部。",
                "入声字普通话多读阴平/阳平，此处按中古音归仄，勿用拼音判平仄。",
                "同一字可属多个韵部（多音字），查询时按出现过的音汇总。",
                "共享字平仄分歧以主表为准；分歧清单见 pingshui_conflicts.json。",
                "RAW2 独有字已并入（补主表缺字），这些字未经人工逐字核对。",
            ],
        },
        "groups": [{k: g[k] for k in ("name", "tone", "category", "num", "section", "chars")}
                   for g in groups],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    CONFLICTS.write_text(
        json.dumps(
            {
                "meta": {
                    "what": "两表共享字但平仄不同；本项目采用 primary（主表 RAW）。",
                    "count": len(report["conflicts"]),
                },
                "conflicts": report["conflicts"],
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"韵部 {len(groups)}，收字 {len(per_char)}，平仄两读 {mixed}，"
          f"RAW2 补字 {report['added']}，平仄分歧 {len(report['conflicts'])}", file=sys.stderr)

    ok = True
    samples = {"入声字应为仄": ("白国竹石一十客日", "Z"), "常见平声": ("春风天山云人东", "P")}
    for label, (chars, want) in samples.items():
        got = {ch: "".join(sorted(per_char.get(ch, {"?"}))) for ch in chars}
        bad = {ch: v for ch, v in got.items() if want not in v}
        print(f"{label}: {got}", file=sys.stderr)
        if bad:
            ok = False
            print(f"  !! 异常: {bad}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
