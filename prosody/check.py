from .template import Template
from dataclasses import dataclass

@dataclass
class CheckResult:
    ok: bool
    errors: list[str]        # ["孤平", "出韵", "第3字平仄不合"]

def check(poem: str, template: Template, strict: bool = True) -> CheckResult: 
    raise NotImplementedError

def check_line(line: str, pattern: str) -> CheckResult:
    raise NotImplementedError