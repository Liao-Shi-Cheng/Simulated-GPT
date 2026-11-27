"""真实语料上的判定器体检（不是单元测试，是报告里那些数字的来源）。

用法：
    python tests/benchmark_real.py            # 需要先跑过 prepare.py 的语料

输出三段：
    1. 唐诗三百首（人工选本、带体裁标签）里五绝/五律的合律率
    2. 全唐诗里"4 句 × 5 字"作品的格式分布与合律率
    3. 拗律 / 古绝的判定理由抽样，用于人工抽查

为什么合律率不是 100%：选本里的"五言绝句/律诗"混入了古绝、拗律和仄韵诗，
它们本来就不合近体规则；判定器把它们判掉才是对的。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import opencc  # noqa: E402

from prepare import collect, normalize_poem, poem_form, sentences  # noqa: E402
from prosody.check import check  # noqa: E402
from prosody.pingze import PING, ZE, char_pingze, is_cjk  # noqa: E402
from prosody.template import all_templates  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TANG300 = ROOT / "data" / "raw" / "tang" / "tang300.json"


def rows_of(item: dict, conv: opencc.OpenCC) -> list[str]:
    poem = normalize_poem(item, conv, min_chars=1)
    return ["".join(ch for ch in s if is_cjk(ch)) for s in sentences(poem)]


def judge(rows: list[str], form: str):
    for t in all_templates(form):
        res = check("\n".join(rows), t, strict=False, allow_teao=True)
        if res.ok:
            return t, res
    best = min((len(check("\n".join(rows), t, strict=False, allow_teao=True).errors), i)
               for i, t in enumerate(all_templates(form)))
    t = all_templates(form)[best[1]]
    return None, check("\n".join(rows), t, strict=False, allow_teao=True)


def benchmark_tang300() -> None:
    if not TANG300.exists():
        print(f"!! 找不到 {TANG300}", file=sys.stderr)
        return
    conv = opencc.OpenCC("t2s.json")
    data = json.loads(TANG300.read_text(encoding="utf-8"))
    for tag, form in (("五言绝句", "五绝"), ("五言律诗", "五律")):
        sub = [d for d in data if tag in d.get("tags", [])]
        ok, fails = 0, []
        for d in sub:
            rows = rows_of(d, conv)
            tpl, res = judge(rows, form)
            if tpl:
                ok += 1
            else:
                fails.append((d["title"], rows, res.errors[:2]))
        rate = 100 * ok / len(sub) if sub else 0
        print(f"\n== 唐诗三百首 {tag}: {ok}/{len(sub)} 合律 ({rate:.1f}%)")
        for title, rows, errs in fails:
            print(f"   {title}: {'/'.join(rows)}  ← {errs}")


def benchmark_corpus() -> None:
    stats = collect(ROOT / "data" / "raw" / "tang")
    form = Counter()
    rhyme_kind = Counter()
    reason = Counter()
    total = 0
    for poem in stats.poems:
        first, rows = poem_form(poem)
        if len(rows) != 4 or any(len(r) != 5 for r in rows):
            continue
        total += 1
        feet = [char_pingze(rows[i][-1]) for i in (1, 3)]
        if all(f == ZE for f in feet):
            rhyme_kind["仄韵"] += 1
        elif all(f == PING for f in feet):
            rhyme_kind["平韵"] += 1
        else:
            rhyme_kind["混/缺"] += 1
        if first is None:
            form["未匹配"] += 1
            # 用最接近的格式统计失败原因，才能看出是"平仄错"还是"韵错"
            best = min((len(check("\n".join(rows), t, strict=False, allow_teao=True).errors), i)
                       for i, t in enumerate(all_templates()))
            errs = check("\n".join(rows), all_templates()[best[1]],
                         strict=False, allow_teao=True).errors
        else:
            form[first] += 1
            errs = []
        for e in errs:
            for kw in ("平仄不合", "孤平", "三平调", "未收录", "不是平声", "出韵", "不入韵"):
                if kw in e:
                    reason[kw] += 1
    print(f"\n== 全唐诗 4 句×5 字作品: {total} 首")
    print("   格式分布", dict(form.most_common()))
    print("   韵脚类型", dict(rhyme_kind))
    valid = sum(v for k, v in form.items() if k != "未匹配")
    print(f"   合律率 {valid / total:.2%}（其中平韵作品内合律率 "
          f"{valid / max(rhyme_kind['平韵'], 1):.2%}）")
    print("   失败时的规则命中（一首可命中多条）", dict(reason.most_common()))


def main() -> int:
    benchmark_tang300()
    benchmark_corpus()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
