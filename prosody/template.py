# prosody/template.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Template:
    form: str                    # "五绝"
    first: str                   # "A" | "B" | "C" | "D"
    lines: tuple[str, ...]       # ("ZZPPZ", "PPZZP", "PPPZZ", "ZZZPP")
    rhyme_lines: tuple[int, ...] # 0-indexed，如 (1, 3)

def build_template(first: str, form: str = "五绝") -> Template: 
    raise NotImplementedError

def all_templates(form: str = "五绝") -> list[Template]: 
    raise NotImplementedError