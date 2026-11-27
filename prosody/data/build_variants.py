"""生成 variants.json：异体字/俗字 → 通行字。

为什么需要：平水韵表用字与唐诗用字都不统一，``疎/疏``、``劒/剑``、``猨/猿``
这类异体字 opencc 的 t2s 不会转换，查表就会查不到（全唐诗里约 1% 的字次）。
把它们归一到通行字后，语料去重、词表规模、格律判定三处都受益。

用法：
    python prosody/data/build_variants.py                          # 只用内置表
    python prosody/data/build_variants.py --unihan Unihan_Variants.txt  # 叠加 Unihan 推导

``--unihan`` 需要 Unicode 公开数据（https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip 里的
Unihan_Variants.txt），仓库里不放这个 8MB 的文件，所以默认只跑内置表。
内置表是人工核对的，Unihan 推导是补充，二者合并后统一收敛到"能在韵表里查到的通行字"。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import opencc

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parents[1] / "data" / "raw" / "tang"
OUT = HERE / "variants.json"

# 人工核对过的异体字 → 通行字。只收"字形不同但同音同义"的，形近字（如 己/已）不收。
CURATED = {
    "疎": "疏", "劒": "剑", "猨": "猿", "慙": "惭", "徧": "遍", "斾": "旆",
    "蘂": "蕊", "堦": "阶", "覩": "睹", "臯": "皋", "廻": "回", "飜": "翻",
    "髪": "发", "暎": "映", "妬": "妒", "隣": "邻", "檝": "楫", "呌": "叫",
    "竝": "并", "珪": "圭", "顇": "悴", "牋": "笺", "顦": "憔", "罇": "樽",
    "鏁": "锁", "逈": "迥", "鵶": "鸦", "讐": "仇", "緜": "绵", "缾": "瓶",
    "壻": "婿", "垅": "垄", "栢": "柏", "粧": "妆", "棃": "梨", "鸎": "莺",
    "筯": "箸", "帬": "裙", "碁": "棋", "牕": "窗", "藂": "丛", "趂": "趁",
    "邨": "村", "懽": "欢", "悮": "误", "飡": "餐", "虵": "蛇", "徴": "征",
    "峩": "峨", "袴": "裤", "輭": "软", "畧": "略", "汚": "污", "舃": "舄",
    "効": "效", "欵": "款", "衞": "卫", "穉": "稚", "怱": "匆", "犂": "犁",
    "瓌": "瑰", "鳯": "凤", "秔": "粳", "撃": "击", "頳": "赪", "嗁": "啼",
    "隟": "隙", "臙": "胭", "覰": "觑", "蟇": "蟆", "倐": "倏", "鄽": "廛",
    "駈": "驱", "澘": "潸", "顋": "腮", "韈": "袜", "韤": "袜", "箆": "篦",
    "笻": "筇", "葅": "菹", "踈": "疏", "矟": "槊", "麞": "獐", "齅": "嗅",
    "薫": "熏", "顚": "颠", "潄": "漱", "崐": "昆", "稉": "粳", "忩": "匆",
    "虀": "齑", "剏": "创", "擕": "携", "竃": "灶", "敭": "扬", "塠": "堆",
    "磎": "溪", "儛": "舞", "旍": "旌", "蠒": "茧", "茘": "荔", "慿": "凭",
    "藳": "稿", "糢": "模", "苽": "菰", "嬝": "袅", "繍": "绣", "裩": "裈",
    "涙": "泪", "筓": "笄", "尫": "尪", "蔲": "蔻", "扠": "叉", "柹": "柿",
    "戞": "戛", "熖": "焰", "蝱": "虻", "橰": "槔", "嗸": "嗷", "朞": "期",
    "厫": "廒", "翶": "翱", "眽": "脉", "浄": "净", "桒": "桑", "麏": "麇",
    "枿": "蘖", "搘": "支", "媿": "愧", "厠": "厕", "慾": "欲", "麤": "粗",
    "黏": "粘", "羗": "羌", "徃": "往", "迺": "乃", "廼": "乃", "琹": "琴",
    "綵": "彩", "顔": "颜", "囘": "回", "煇": "辉", "逺": "远", "攷": "考",
}


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF or 0x20000 <= o <= 0x2FFFF


def load_table_chars() -> set[str]:
    payload = json.loads((HERE / "pingshui.json").read_text(encoding="utf-8"))
    return {ch for g in payload["groups"] for ch in g["chars"]}


def unihan_map(path: Path) -> dict[str, list[str]]:
    """解析 Unihan_Variants.txt，返回 字 → 候选通行字（按可信度排序）。"""
    out: dict[str, list[str]] = {}
    fields = ("kSimplifiedVariant", "kZVariant", "kSemanticVariant")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[1] not in fields:
            continue
        src = chr(int(parts[0][2:], 16))
        for item in parts[2].split():
            dst = chr(int(item.split("<")[0][2:], 16))
            out.setdefault(src, []).append(dst)
    return out


def resolve(ch: str, table: set[str], conv: opencc.OpenCC, cands: dict[str, list[str]],
            depth: int = 0) -> str | None:
    """把一个字收敛到韵表里的通行字：先试 t2s，再试异体字候选。"""
    if ch in table:
        return ch
    if depth > 4:
        return None
    simplified = conv.convert(ch)
    if simplified != ch:
        got = resolve(simplified, table, conv, cands, depth + 1)
        if got:
            return got
    for nxt in cands.get(ch, []):
        got = resolve(nxt, table, conv, cands, depth + 1)
        if got:
            return got
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 variants.json")
    parser.add_argument("--unihan", type=Path, help="Unihan_Variants.txt 路径（可选）")
    parser.add_argument("--corpus", default=str(CORPUS), help="语料目录，用于只收真实出现过的异体字")
    args = parser.parse_args()

    table = load_table_chars()
    conv = opencc.OpenCC("t2s.json")

    cands: dict[str, list[str]] = {ch: [dst] for ch, dst in CURATED.items()}
    if args.unihan:
        if not args.unihan.is_file():
            print(f"!! 找不到 {args.unihan}", file=sys.stderr)
            return 1
        for src, dsts in unihan_map(args.unihan).items():
            cands.setdefault(src, [])
            for dst in dsts:
                if dst not in cands[src]:
                    cands[src].append(dst)

    corpus_dir = Path(args.corpus)
    if corpus_dir.is_dir():
        words: set[str] = set()
        for path in sorted(corpus_dir.glob("*.json")):
            for poem in json.loads(path.read_text(encoding="utf-8")):
                for line in poem.get("paragraphs", []):
                    words.update(ch for ch in conv.convert(line) if is_cjk(ch))
        candidates = sorted(words)
    else:
        print(f"!! 语料目录 {corpus_dir} 不存在，只从内置表推导", file=sys.stderr)
        candidates = sorted(cands)

    mapping = {ch: got for ch in candidates
               if ch not in table and (got := resolve(ch, table, conv, cands))}
    mapping = {ch: got for ch, got in mapping.items() if got != ch}

    payload = {
        "meta": {
            "what": "异体字/俗字 → 通行字（平水韵表可查）",
            "usage": "prosody.variants.normalize()；prepare.py 也用它归一化语料",
            "count": len(mapping),
            "sources": [
                "内置人工核对表（CURATED）",
                "Unihan_Variants.txt 推导" if args.unihan else "未使用 Unihan",
            ],
            "notes": [
                "只收字形不同、同音同义的异体；形近字（己/已、戊/戌）绝不合并。",
                "映射目标已收敛到平水韵表里能查到的字，否则不产出这条映射。",
            ],
        },
        "map": dict(sorted(mapping.items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"异体字映射 {len(mapping)} 条 → {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
