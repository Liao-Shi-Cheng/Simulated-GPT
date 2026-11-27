"""合律判定测试：逐句平仄、孤平、三平调、韵、特拗，以及真实唐诗的回归。"""

import unittest

from prosody.check import check, check_line, parse_poem
from prosody.template import all_templates, build_template


def ok(line, pattern, **kw):
    return check_line(line, pattern, **kw).ok


class TestParsePoem(unittest.TestCase):
    def test_split_styles(self):
        flat = "白日依山尽黄河入海流欲穷千里目更上一层楼"
        want = ["白日依山尽", "黄河入海流", "欲穷千里目", "更上一层楼"]
        self.assertEqual(parse_poem(flat), want)
        self.assertEqual(parse_poem("\n".join(want)), want)
        self.assertEqual(parse_poem("，".join(want)), want)
        self.assertEqual(parse_poem("  ".join(want) + "\n"), want)
        self.assertEqual(
            parse_poem("白日依山尽，黄河入海流。\n欲穷千里目，更上一层楼。"), want
        )

    def test_structure_mismatch(self):
        self.assertIsNone(parse_poem("白日依山尽"))
        self.assertIsNone(parse_poem("白日依山尽\n黄河入海流\n欲穷千里目"))
        self.assertIsNone(parse_poem("白日依山尽尽\n黄河入海流\n欲穷千里目\n更上一层楼"))


class TestCheckLine(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(ok("白日依山尽", "ZZPPZ"))
        self.assertFalse(ok("白日依山尽", "PPZZP"))

    def test_length(self):
        r = check_line("白日依山", "ZZPPZ")
        self.assertFalse(r.ok)
        self.assertTrue(any("句长" in e for e in r.errors))

    def test_unrecorded_char(self):
        r = check_line("白日依〇尽", "ZZPPZ")
        self.assertFalse(r.ok)
        self.assertTrue(any("未收录" in e for e in r.errors))

    def test_strict_vs_flex(self):
        # 欲穷千里目 = 仄平仄仄，定式 PPPZZ，首字"一不论"
        self.assertFalse(ok("欲穷千里目", "PPPZZ", strict=True))
        self.assertTrue(ok("欲穷千里目", "PPPZZ", strict=False))
        # 第二字（二分明）不能放
        self.assertFalse(ok("春色千里目", "PPPZZ", strict=False))

    def test_three_ping(self):
        r = check_line("东风花飞天", "PPZZP", strict=False)
        self.assertIn("三平调", r.errors)

    def test_three_ping_needs_certain_ping(self):
        """多音字不能凑三平调：王孙归不归 的"不"读仄声。"""
        self.assertTrue(ok("王孙归不归", "PPZZP", strict=False))

    def test_gujiu(self):
        r = check_line("月明照客愁", "PPZZP", strict=False)
        self.assertIn("孤平", r.errors)

    def test_gujiu_rescue(self):
        # 仄平平仄平：第 1 字用仄后以第 3 字平声相救
        self.assertTrue(ok("月明花客愁", "PPZZP", strict=False, allow_gujiu=True))
        self.assertFalse(ok("月明花客愁", "PPZZP", strict=True, allow_gujiu=False))
        self.assertTrue(ok("月明花客愁", "PPZZP", strict=True, allow_gujiu=True))

    def test_teao(self):
        # 平平仄平仄 = 定式 平平平仄仄 的三四字互换
        self.assertFalse(ok("春风夜明月", "PPPZZ", strict=True))
        self.assertTrue(ok("春风夜明月", "PPPZZ", strict=True, allow_teao=True))
        # 特拗只对 C 型句生效，A 型句不能借此蒙混
        self.assertFalse(ok("春风夜明月", "ZZPPZ", strict=True, allow_teao=True))


class TestCheckPoem(unittest.TestCase):
    # 名篇回归：律绝必须过，古绝必须不过（不是判定器的错）
    LUSHI = {
        "登鹳雀楼": "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼",
        "相思": "红豆生南国\n春来发几枝\n愿君多采撷\n此物最相思",
        "送别": "山中相送罢\n日暮掩柴扉\n春草年年绿\n王孙归不归",
    }
    GUJUE = {
        "静夜思": "床前明月光\n疑是地上霜\n举头望明月\n低头思故乡",
        "春晓": "春眠不觉晓\n处处闻啼鸟\n夜来风雨声\n花落知多少",
        "鹿柴": "空山不见人\n但闻人语响\n返景入深林\n复照青苔上",
    }

    def test_famous_lvjue_pass(self):
        for name, poem in self.LUSHI.items():
            with self.subTest(name=name):
                hits = [t.first for t in all_templates()
                        if check(poem, t, strict=False, allow_teao=True).ok]
                self.assertTrue(hits, f"{name} 应能匹配某个格式")

    def test_famous_gujue_fail(self):
        for name, poem in self.GUJUE.items():
            with self.subTest(name=name):
                hits = [t.first for t in all_templates()
                        if check(poem, t, strict=False, allow_teao=True).ok]
                self.assertEqual(hits, [], f"{name} 是古绝，不应判为合律")

    def test_rhyme_lines(self):
        """首句入韵格式：第 1、2、4 句押韵。"""
        poem = "春风入夜凉\n月落满庭香\n对影成三客\n何时共一觞"
        t = build_template("B")
        self.assertEqual(t.rhyme_lines, (0, 1, 3))
        self.assertTrue(check(poem, t).ok)
        for other in all_templates():
            if other.first != "B":
                self.assertFalse(check(poem, other).ok)

    def test_chuyun(self):
        """韵脚跨韵部即出韵：凉/香 属七阳，樽 属十三元。"""
        poem = "春风入夜凉\n月落满庭香\n对影成三客\n何时共一樽"
        r = check(poem, build_template("B"))
        self.assertFalse(r.ok)
        self.assertTrue(any("出韵" in e for e in r.errors), r.errors)

    def test_yun_foot_must_be_ping(self):
        poem = "东风入夜凉\n月落满庭香\n对影成三客\n何时共一觞".replace("觞", "客")
        r = check(poem, build_template("B"))
        self.assertFalse(r.ok)

    def test_structure_error(self):
        r = check("白日依山尽", build_template("A"))
        self.assertFalse(r.ok)
        self.assertTrue(any("结构" in e for e in r.errors))


if __name__ == "__main__":
    unittest.main()
