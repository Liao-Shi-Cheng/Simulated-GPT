"""格律引擎：平仄 / 韵部 / 句式推导 / 合律判定。

对外主接口（工作说明 §6.1）::

    from prosody import build_template, all_templates, check, rhyme_group

约定：P=平，Z=仄，"PZ"=平仄两读；判定用平水韵（中古音），不要用拼音。
"""

from .check import CheckResult, check, check_line, parse_poem
from .pingze import BOTH, PING, ZE, char_pingze, load_pingshuiyun
from .rhyme import chars_in_group, rhyme_group, rhyme_groups, top_groups
from .template import Template, all_templates, build_template
from .variants import normalize

__all__ = [
    "BOTH", "PING", "ZE",
    "CheckResult", "Template",
    "all_templates", "build_template", "chars_in_group", "char_pingze",
    "check", "check_line", "load_pingshuiyun", "normalize", "parse_poem",
    "rhyme_group", "rhyme_groups", "top_groups",
]
