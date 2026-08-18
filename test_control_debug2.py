# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SUBTITLE_PATTERNS, SLASH_REPLACEMENTS
import re

text = "《操控游戏》\n池昌旭/都敬秀/李光洙主演犯罪剧集\n全12集 韩语中字\n见平👇 ​ ​​​"
for sub_pat in SUBTITLE_PATTERNS:
    sub_idx = text.find(sub_pat)
    if sub_idx != -1:
        before = text[:sub_idx].rstrip()
        original_before = before
        for old, new in sorted(SLASH_REPLACEMENTS.items(), key=lambda x: len(x[0]), reverse=True):
            before = before.replace(old, new)
        print(f"original_before={original_before!r}")
        print(f"before={before!r}")
        lang_part = before.split('\n')[-1].strip()
        print(f"lang_part initial={lang_part!r}")
        lang_part = re.sub(r'全\d+集$', '', lang_part).strip()
        print(f"after remove 全N集={lang_part!r}")
        lang_part = re.sub(r'第\d+季$', '', lang_part).strip()
        print(f"after remove 第N季={lang_part!r}")
        lang_part = lang_part.replace(' ', '')
        print(f"final lang_part={lang_part!r}")
        break
