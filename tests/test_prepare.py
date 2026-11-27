"""数据管线测试：归一化、两级去重、切分、词表、编码。"""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import prepare
from prepare import Poem, build_vocab, collect, encode, normalize_poem, split_poems


def item(title, paragraphs):
    return {"title": title, "author": "test", "paragraphs": paragraphs}


class TestPrepare(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        poems = [
            item("律绝", ["白日依山盡，黃河入海流。", "欲窮千里目，更上一層樓。"]),
            item("重复", ["白日依山盡，黃河入海流。", "欲窮千里目，更上一層樓。"]),
            # 只差标点：算近似重复
            item("近似", ["白日依山尽。黄河入海流", "欲穷千里目，更上一层楼"]),
            item("异体", ["疎雨滴高梧，微風颯然至。", "故人久不來，幽鳥啼何處。"]),
            item("太短", ["春"]),
        ]
        (self.raw / "poet.tang.0.json").write_text(
            json.dumps(poems, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_collect_and_dedupe(self):
        stats = collect(self.raw, min_chars=10)
        self.assertEqual(stats.raw_poems, 5)
        self.assertEqual(stats.exact_dup, 1)
        self.assertEqual(stats.near_dup, 1)
        self.assertEqual(stats.dropped_short, 1)
        self.assertEqual(len(stats.poems), 2)
        self.assertEqual([p.title for p in stats.poems], ["律绝", "异体"])

    def test_normalize(self):
        conv = prepare.opencc.OpenCC("t2s.json")
        p = normalize_poem(item("x", ["白日依山盡，黃河入海流。"]), conv, min_chars=1)
        self.assertEqual(p.text, "白日依山尽，黄河入海流。")   # 繁转简，标点保留
        p = normalize_poem(item("x", ["疎雨滴高梧。"]), conv, min_chars=1)
        self.assertEqual(p.text, "疏雨滴高梧。")               # 异体字归一
        self.assertEqual(p.clean, "疏雨滴高梧")

    def test_short_dropped(self):
        conv = prepare.opencc.OpenCC("t2s.json")
        self.assertIsNone(normalize_poem(item("x", ["春"]), conv, min_chars=10))

    def test_split_is_by_poem_and_deterministic(self):
        poems = [Poem(lines=[f"第{i}句"], clean=f"第{i}句") for i in range(100)]
        a = split_poems(poems, seed=1337)
        b = split_poems(poems, seed=1337)
        self.assertEqual(a.keys(), {"train", "val", "test"})
        self.assertEqual((len(a["train"]), len(a["val"]), len(a["test"])), (90, 5, 5))
        self.assertEqual([p.clean for p in a["train"]], [p.clean for p in b["train"]])
        ids = [p.clean for p in a["train"] + a["val"] + a["test"]]
        self.assertEqual(len(ids), len(set(ids)))            # 一首诗只出现在一个 split

    def test_vocab_and_encode(self):
        poems = [Poem(lines=["春风，春风"], clean="春风春风")]
        itos = build_vocab(poems, min_freq=1)
        self.assertEqual(itos[0], "<unk>")
        self.assertEqual(itos[1], "\n")      # 换行是作品分隔符，必须入表
        for ch in "春风，":
            self.assertIn(ch, itos)
        # min_freq 过滤：只出现 1 次的字被丢弃
        itos = build_vocab(poems, min_freq=2)
        self.assertNotIn("，", itos)
        self.assertIn("春", itos)

        arr = encode(poems, itos)
        self.assertEqual(arr.dtype, np.uint16)
        self.assertEqual(arr.size, len("春风，春风") + 1)      # 末尾补一个换行
        self.assertEqual(int(arr[-1]), itos.index("\n"))


if __name__ == "__main__":
    unittest.main()
