"""锁定 §3.3.2 的四个格式推导结果。

规则理解错一个字符会导致全部实验作废，所以这里逐字对表，不用"看起来对"判断。
"""

import unittest

from prosody.template import Template, all_templates, build_template, patterns


class TestTemplate(unittest.TestCase):
    # 与工作说明 §3.3.2 表格完全一致的期望值
    EXPECTED = {
        "A": (("ZZPPZ", "PPZZP", "PPPZZ", "ZZZPP"), (1, 3), False),
        "B": (("PPZZP", "ZZZPP", "ZZPPZ", "PPZZP"), (0, 1, 3), True),
        "C": (("PPPZZ", "ZZZPP", "ZZPPZ", "PPZZP"), (1, 3), False),
        "D": (("ZZZPP", "PPZZP", "PPPZZ", "ZZZPP"), (0, 1, 3), True),
    }

    def test_four_patterns(self):
        self.assertEqual(
            patterns(),
            {"A": "ZZPPZ", "B": "PPZZP", "C": "PPPZZ", "D": "ZZZPP"},
        )

    def test_derivation_matches_table(self):
        for first, (lines, rhyme_lines, first_rhymes) in self.EXPECTED.items():
            with self.subTest(first=first):
                t = build_template(first)
                self.assertEqual(t.form, "五绝")
                self.assertEqual(t.first, first)
                self.assertEqual(t.lines, lines)
                self.assertEqual(t.rhyme_lines, rhyme_lines)
                self.assertEqual(0 in t.rhyme_lines, first_rhymes)

    def test_dui_and_nian(self):
        """联内对（2/4 字相反）与联间粘（2 字相同），这是格式的唯一来源。"""
        for t in all_templates():
            with self.subTest(first=t.first):
                for i in (1, 3):          # 每联下句与上句"对"
                    self.assertNotEqual(t.lines[i][1], t.lines[i - 1][1])
                    self.assertNotEqual(t.lines[i][3], t.lines[i - 1][3])
                self.assertEqual(t.lines[2][1], t.lines[1][1])  # 联间"粘"

    def test_even_lines_rhyme(self):
        """偶数句必押韵，奇数句不入韵（首句是否入韵由首句句式决定）。"""
        for t in all_templates():
            with self.subTest(first=t.first):
                self.assertEqual(t.lines[1][-1], "P")
                self.assertEqual(t.lines[3][-1], "P")
                self.assertEqual(t.lines[2][-1], "Z")
                self.assertEqual(t.lines[0][-1], "P" if 0 in t.rhyme_lines else "Z")

    def test_all_templates_order(self):
        self.assertEqual([t.first for t in all_templates()], ["A", "B", "C", "D"])

    def test_frozen_and_hashable(self):
        t = build_template("A")
        self.assertIsInstance(t, Template)
        with self.assertRaises(Exception):
            t.first = "B"  # type: ignore[misc]
        self.assertEqual(len({build_template(x) for x in "ABCD"}), 4)

    def test_no_three_ping_in_templates(self):
        """模板本身不许出现三平调，也不许句末三字全平。"""
        for t in all_templates():
            for line in t.lines:
                self.assertNotEqual(line[-3:], "PPP")

    def test_wulu(self):
        """五律 = 同一条对/粘规则往后推两联。"""
        want = {
            "A": "ABCDABCD",
            "B": "BDABCDAB",
            "C": "CDABCDAB",
            "D": "DBCDABCD",
        }
        rhyme = {"A": (1, 3, 5, 7), "B": (0, 1, 3, 5, 7),
                 "C": (1, 3, 5, 7), "D": (0, 1, 3, 5, 7)}
        for first, seq in want.items():
            with self.subTest(first=first):
                t = build_template(first, form="五律")
                letters = [next(k for k, v in patterns().items() if v == pz) for pz in t.lines]
                self.assertEqual("".join(letters), seq)
                self.assertEqual(t.rhyme_lines, rhyme[first])

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            build_template("E")
        with self.assertRaises(ValueError):
            build_template("")
        with self.assertRaises(ValueError):
            build_template("A", form="七绝")
        # 大小写与空白应被容错
        self.assertEqual(build_template(" a ").lines, build_template("A").lines)


if __name__ == "__main__":
    unittest.main()
