# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SUBTITLE_PATTERNS

text = "《泥人哥连出世记》\n德国表现主义电影代表作\n默片 中文字幕\n见平👇"
for sub_pat in SUBTITLE_PATTERNS:
    sub_idx = text.find(sub_pat)
    print(f"sub_pat={sub_pat!r}, sub_idx={sub_idx}")
