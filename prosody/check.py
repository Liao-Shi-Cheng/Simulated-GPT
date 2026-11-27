"""合律判定。

判定分三层，顺序固定：

1. 结构：句数、每句字数（默认五绝 = 4 句 × 5 字）
2. 逐句平仄：模板存**严格**平仄值，"一三五不论"只在 ``strict=False`` 时放宽
3. 韵：韵脚必须平声、一韵到底（韵部锁定）

孤平 / 三平调是"放宽或拗救之后的残局"：严格照模板写永远不会触发，
但只要允许一三五不论或变体句式，就必须查（§7.1 的坑）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .pingze import PING, char_pingze, is_cjk, matches
from .rhyme import rhyme_groups
from .template import FORMS, Template, patterns, variants


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]        # ["孤平", "出韵", "第3字平仄不合"]

    def extend(self, prefix: str, other: "CheckResult") -> None:
        self.errors.extend(f"{prefix}{e}" for e in other.errors)
        self.ok = not self.errors


def line_length(form: str = "五绝") -> int:
    """每句字数（五言 = 5）。句式表的四个句式长度必须一致。"""
    if form not in FORMS:
        raise ValueError(f"暂不支持的形式: {form!r}")
    lengths = {len(p) for p in patterns().values()}
    if len(lengths) != 1:
        raise AssertionError(f"句式长度不一致: {sorted(lengths)}")
    return lengths.pop()


def _free_positions(n: int) -> frozenset[int]:
    """一三五不论：五言放开第 1、3 字（0-indexed 0、2），句末永远不放开。"""
    return frozenset(i for i in range(n - 1) if i % 2 == 0)


def _pattern_candidates(pattern: str, allow_teao: bool, allow_gujiu: bool) -> list[str]:
    """基准句式 + 启用的变体句式。"""
    cands = [pattern]
    for name, enabled in (("teao", allow_teao), ("gujiu", allow_gujiu)):
        if not enabled:
            continue
        item = variants().get(name)
        if item and patterns().get(item["base"]) == pattern:
            cands.append(item["pz"])
    return cands


def check_line(
    line: str,
    pattern: str,
    *,
    strict: bool = True,
    allow_teao: bool = False,
    allow_gujiu: bool = False,
) -> CheckResult:
    """判定单句是否符合给定平仄串。

    ``strict=True``：逐字与模板一致；``strict=False``：只固定第 2、4 字和句末。
    变体句式（特拗 / 孤平救）需显式开启，默认关闭（§3.3.3）。
    """
    errors: list[str] = []
    line = line.strip()
    if len(line) != len(pattern):
        return CheckResult(False, [f"句长应为{len(pattern)}字，实际{len(line)}字"])

    pz = [char_pingze(ch) for ch in line]
    for i, (ch, actual) in enumerate(zip(line, pz)):
        if actual is None:
            errors.append(f"第{i + 1}字「{ch}」未收录平水韵")

    candidates = _pattern_candidates(pattern, allow_teao, allow_gujiu)
    free = frozenset() if strict else _free_positions(len(pattern))
    fixed = [i for i in range(len(pattern)) if i not in free]

    def fits(cand: str) -> list[str]:
        bad: list[str] = []
        for i in fixed:
            actual = pz[i]
            if actual is None:
                continue                      # 上面已报"未收录"，不重复报
            if not matches(actual, cand[i]):
                bad.append(f"第{i + 1}字平仄不合（{line[i]}:{actual}，应为{cand[i]}）")
        return bad

    results = [fits(c) for c in candidates]
    best = min(results, key=len)
    if best:
        errors.extend(best)

    # ---- 三平调：句末三字全平，任何情况都不合法 ----
    # 这里要求确定读平声（"P"），不能用"PZ"凑数：否则 王孙归不归 这种
    # "不"字多音的情况会被误判成三平调。
    if len(line) >= 3 and all(p == PING for p in pz[-3:]):
        errors.append("三平调")

    # ---- 孤平：只在确定的平收句（韵句）上判定 ----
    # 韵脚是多音字（"PZ"）时无从确定是否平收，宁可不报，避免误判真唐诗。
    if pz[-1] == PING:
        ping_others = [i for i in range(len(line) - 1) if matches(pz[i], PING)]
        if len(ping_others) == 0 or (len(ping_others) == 1 and ping_others[0] != len(line) - 2):
            errors.append("孤平")

    return CheckResult(not errors, errors)


def _clean(text: str) -> str:
    """只保留汉字。标点是断句信息，判定时不需要。"""
    return "".join(ch for ch in text if is_cjk(ch))


def parse_poem(poem: str, form: str = "五绝") -> list[str] | None:
    """把整首诗拆成若干句，每句只含汉字；结构不符返回 ``None``。

    两种输入都接受：带换行（每行一句，可带标点）或纯 20 字连写。
    """
    if form not in FORMS:
        raise ValueError(f"暂不支持的形式: {form!r}")
    n_lines = FORMS[form]

    line_len = line_length(form)
    by_line = [c for c in (_clean(part) for part in poem.splitlines()) if c]
    if len(by_line) == n_lines and all(len(c) == line_len for c in by_line):
        return by_line

    flat = _clean(poem)
    if len(flat) == n_lines * line_len:
        return [flat[i * line_len:(i + 1) * line_len] for i in range(n_lines)]
    return None


def check(
    poem: str,
    template: Template,
    strict: bool = True,
    allow_teao: bool = False,
    allow_gujiu: bool = False,
) -> CheckResult:
    """判定整首诗是否合律。

    ``poem`` 是纯文本（不含标点也可以），内部按 ``template.form`` 切分。
    """
    lines = parse_poem(poem, template.form)
    if lines is None:
        return CheckResult(False, [f"结构不符：应为 {FORMS[template.form]} 句×"
                                   f"{line_length(template.form)} 字，"
                                   f"实际得到 {len(_clean(poem))} 字"])
    if len(lines) != len(template.lines):
        return CheckResult(False, [f"结构不符：格式有 {len(template.lines)} 句，"
                                   f"实际 {len(lines)} 句"])

    result = CheckResult(True, [])
    for i, (line, pattern) in enumerate(zip(lines, template.lines)):
        result.extend(
            f"第{i + 1}句：",
            check_line(line, pattern, strict=strict, allow_teao=allow_teao, allow_gujiu=allow_gujiu),
        )

    # ---- 韵：韵脚平声 + 一韵到底 ----
    common: set[str] | None = None
    for idx in template.rhyme_lines:
        ch = lines[idx][-1]
        tone = char_pingze(ch)
        if tone is None:
            result.errors.append(f"第{idx + 1}句韵脚「{ch}」未收录平水韵")
            continue
        if not matches(tone, PING):
            result.errors.append(f"第{idx + 1}句韵脚「{ch}」不是平声")
            continue
        groups = set(rhyme_groups(ch))
        common = groups if common is None else common & groups
    if common is not None and not common:
        feet = "、".join(lines[i][-1] for i in template.rhyme_lines)
        result.errors.append(f"出韵：韵脚「{feet}」不在同一平声韵部")

    # 多音字（"PZ"）句末无法确定是否入韵（如 山中相送罢 的"罢"读去声），
    # 只对确定读平声的句末报这个错。
    for idx, line in enumerate(lines):
        if idx not in template.rhyme_lines and char_pingze(line[-1]) == PING:
            result.errors.append(f"第{idx + 1}句平收，但该格式此句不入韵")

    result.ok = not result.errors
    return result
