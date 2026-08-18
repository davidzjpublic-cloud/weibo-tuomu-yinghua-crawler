# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SUBTITLE_PATTERNS

text = "《操控游戏》\n池昌旭/都敬秀/李光洙主演犯罪剧集\n全12集 韩语中字\n见平👇 ​ ​​​"
for sub_pat in SUBTITLE_PATTERNS:
    sub_idx = text.find(sub_pat)
    if sub_idx != -1:
        before = text[:sub_idx].rstrip()
        print(f"sub_pat={sub_pat!r}, sub_idx={sub_idx}")
        print(f"before={before!r}")
        print(f"before[-10:]={before[-10:]!r}")
        break
