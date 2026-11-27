"""平水韵表的数据质量测试：入声、多音字、韵部数量。"""

import unittest

from prosody.pingze import (
    BOTH,
    PING,
    ZE,
    char_groups,
    char_pingze,
    group_info,
    group_names,
    load_pingshuiyun,
    matches,
)


class TestPingze(unittest.TestCase):
    def test_ru_sheng_is_ze(self):
        """入声字普通话读平/上/去，但在平水韵里是仄——这是不能用拼音判平仄的原因。"""
        for ch in "白国竹石一十客日发月入":
            with self.subTest(ch=ch):
                self.assertEqual(char_pingze(ch), ZE)

    def test_common_ping(self):
        for ch in "春风天山云人东":
            with self.subTest(ch=ch):
                self.assertEqual(char_pingze(ch), PING)

    def test_polyphone(self):
        for ch in "中看思长教为":
            with self.subTest(ch=ch):
                self.assertEqual(char_pingze(ch), BOTH)

    def test_not_in_table(self):
        for ch in ("〇", "A", "，", "", " ", "𠀀"):
            with self.subTest(ch=ch):
                self.assertIsNone(char_pingze(ch))
                self.assertEqual(char_groups(ch), ())

    def test_gap_fix(self):
        """主表漏收的常用平声韵脚必须能查到（先/槎 曾被只收在仄声韵部）。"""
        self.assertIn("一先", char_groups("先"))
        self.assertIn(PING, char_pingze("先"))
        self.assertIn("六麻", char_groups("槎"))

    def test_table_shape(self):
        self.assertEqual(len(group_names()), 106)
        self.assertEqual(len(group_names(PING)), 30)
        self.assertEqual(len(group_names(ZE)), 76)
        self.assertIn("一东", group_names(PING))
        self.assertIn("四寘", group_names(ZE))

    def test_groups_unique_and_canonical(self):
        groups = char_groups("逢")
        self.assertEqual(len(groups), len(set(groups)))
        self.assertIn("三江", groups)
        # 韵书顺序：一东 在 二冬 之前
        self.assertLess(groups.index("一东"), groups.index("二冬"))

    def test_load_returns_copy(self):
        table = load_pingshuiyun()
        self.assertEqual(table["春"], PING)
        self.assertGreater(len(table), 8000)
        table["春"] = "Z"                     # 改副本不能污染缓存
        self.assertEqual(char_pingze("春"), PING)

    def test_group_info_is_copy(self):
        info = group_info("一东")
        self.assertEqual(info["tone"], PING)
        info["chars"] = ""
        self.assertIn("东", group_info("一东")["chars"])

    def test_matches(self):
        self.assertTrue(matches("P", "P"))
        self.assertTrue(matches("PZ", "P"))
        self.assertTrue(matches("PZ", "Z"))
        self.assertFalse(matches("P", "Z"))
        self.assertFalse(matches(None, "P"))


if __name__ == "__main__":
    unittest.main()
