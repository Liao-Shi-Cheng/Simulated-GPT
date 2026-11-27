"""真实唐诗回归：名家律绝必须判合律，古体/古绝必须判不合律。

这是"判定器有没有判错"的最后一关：单元测试里自造的诗只能证明逻辑自洽，
这里的诗是公认的近体诗（平水韵可查），判错就是引擎错。

注意：唐诗三百首里"五言绝句"一类混有大量古绝（《春晓》《江雪》《鹿柴》
都是仄韵古绝），所以它们出现在 GUJUE 里而不是失败样本。
"""

import unittest

from prosody.check import check
from prosody.template import all_templates


def hits(poem: str, form: str) -> list[str]:
    return [t.first for t in all_templates(form)
            if check(poem, t, strict=False, allow_teao=True).ok]


class TestRealPoems(unittest.TestCase):
    WUJUE = {
        "登鹳雀楼": "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼",
        "相思": "红豆生南国\n春来发几枝\n愿君多采撷\n此物最相思",
        "送别": "山中相送罢\n日暮掩柴扉\n春草年年绿\n王孙归不归",
        "问刘十九": "绿蚁新醅酒\n红泥小火炉\n晚来天欲雪\n能饮一杯无",
        "汾上惊秋": "北风吹白云\n万里渡河汾\n心绪逢摇落\n秋声不可闻",
    }

    WULU = {
        "山居秋暝": "空山新雨后\n天气晚来秋\n明月松间照\n清泉石上流\n"
                    "竹喧归浣女\n莲动下渔舟\n随意春芳歇\n王孙自可留",
        "春望": "国破山河在\n城春草木深\n感时花溅泪\n恨别鸟惊心\n"
                "烽火连三月\n家书抵万金\n白头搔更短\n浑欲不胜簪",
        "赠孟浩然": "吾爱孟夫子\n风流天下闻\n红颜弃轩冕\n白首卧松云\n"
                    "醉月频中圣\n迷花不事君\n高山安可仰\n徒此揖清芬",
        "题破山寺后禅院": "清晨入古寺\n初日照高林\n曲径通幽处\n禅房花木深\n"
                          "山光悦鸟性\n潭影空人心\n万籁此俱寂\n但余钟磬音",
        "汉江临泛": "楚塞三湘接\n荆门九派通\n江流天地外\n山色有无中\n"
                    "郡邑浮前浦\n波澜动远空\n襄阳好风日\n留醉与山翁",
        "过故人庄": "故人具鸡黍\n邀我至田家\n绿树村边合\n青山郭外斜\n"
                    "开轩面场圃\n把酒话桑麻\n待到重阳日\n还来就菊花",
        "终南山": "太乙近天都\n连山接海隅\n白云回望合\n青霭入看无\n"
                  "分野中峰变\n阴晴众壑殊\n欲投人处宿\n隔水问樵夫",
        "蝉": "本以高难饱\n徒劳恨费声\n五更疏欲断\n一树碧无情\n"
              "薄宦梗犹泛\n故园芜已平\n烦君最相警\n我亦举家清",
        "次北固山下": "客路青山外\n行舟绿水前\n潮平两岸阔\n风正一帆悬\n"
                      "海日生残夜\n江春入旧年\n乡书何处达\n归雁洛阳边",
    }

    GUJUE = {
        "静夜思": "床前明月光\n疑是地上霜\n举头望明月\n低头思故乡",
        "春晓": "春眠不觉晓\n处处闻啼鸟\n夜来风雨声\n花落知多少",
        "鹿柴": "空山不见人\n但闻人语响\n返景入深林\n复照青苔上",
        "江雪": "千山鸟飞绝\n万径人踪灭\n孤舟蓑笠翁\n独钓寒江雪",
        "寻隐者不遇": "松下问童子\n言师采药去\n只在此山中\n云深不知处",
    }

    WUGU = {  # 五言古体，句数和字数像五律但平仄/韵都不合近体
        "望岳": "岱宗夫如何\n齐鲁青未了\n造化钟神秀\n阴阳割昏晓\n"
                "荡胸生曾云\n决眦入归鸟\n会当凌绝顶\n一览众山小",
    }

    def test_wujue_pass(self):
        for name, poem in self.WUJUE.items():
            with self.subTest(name=name):
                self.assertTrue(hits(poem, "五绝"), f"{name} 判为不合律")

    def test_wujue_gujue_fail(self):
        for name, poem in self.GUJUE.items():
            with self.subTest(name=name):
                self.assertEqual(hits(poem, "五绝"), [], f"{name} 被误判为合律")

    def test_wulu_pass(self):
        for name, poem in self.WULU.items():
            with self.subTest(name=name):
                self.assertTrue(hits(poem, "五律"), f"{name} 判为不合律")

    def test_wugu_fail(self):
        for name, poem in self.WUGU.items():
            with self.subTest(name=name):
                self.assertEqual(hits(poem, "五律"), [], f"{name} 被误判为合律")

    def test_format_is_unique(self):
        """同一首诗不应同时匹配两个格式（否则格式统计会重复计数）。"""
        for name, poem in self.LUSHI_ALL():
            with self.subTest(name=name):
                found = hits(poem, "五绝") or hits(poem, "五律")
                self.assertEqual(len(found), 1, f"{name} 匹配到多个格式: {found}")

    def LUSHI_ALL(self):
        for name, poem in {**self.WUJUE, **self.WULU}.items():
            yield name, poem


if __name__ == "__main__":
    unittest.main()
