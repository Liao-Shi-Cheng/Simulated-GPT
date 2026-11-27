"""韵部查询测试。"""

import unittest

from prosody.pingze import PING, group_names
from prosody.rhyme import chars_in_group, rhyme_group, rhyme_groups, top_groups


class TestRhyme(unittest.TestCase):
    def test_rhyme_group(self):
        self.assertEqual(rhyme_group("东"), "一东")
        self.assertEqual(rhyme_group("风"), "一东")
        self.assertIsNone(rhyme_group("白"))      # 入声，不是平声韵
        self.assertIsNone(rhyme_group("〇"))

    def test_multi_group_is_intersected_not_guessed(self):
        """兼韵字要给出全部可能韵部，判定时取交集，不能只看第一个。"""
        groups = rhyme_groups("逢")
        self.assertIn("三江", groups)
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(all(g in group_names(PING) for g in groups), True)

    def test_chars_in_group(self):
        chars = chars_in_group("一东")
        self.assertIsInstance(chars, frozenset)
        self.assertIn("东", chars)
        self.assertIn("风", chars)
        self.assertNotIn("冬", chars)             # 冬 在 二冬，邻韵不等于同韵
        self.assertEqual(chars_in_group("上平声一东"), chars)
        self.assertIn("送", chars_in_group("一送"))  # 仄声韵部也能查
        with self.assertRaises(KeyError):
            chars_in_group("三十一东")

    def test_top_groups(self):
        top = top_groups(10)
        self.assertEqual(len(top), 10)
        self.assertEqual(len(set(top)), 10)
        self.assertTrue(all(g in group_names(PING) for g in top))
        self.assertEqual(top_groups(0), [])


if __name__ == "__main__":
    unittest.main()
