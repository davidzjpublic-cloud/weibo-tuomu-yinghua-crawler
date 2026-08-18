# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SUBTITLE_PATTERNS, SLASH_REPLACEMENTS

test_cases = [
    "《操控游戏》\n池昌旭/都敬秀/李光洙主演犯罪剧集\n全12集 韩语中字\n见平👇 ​ ​​​",
    "《爱情赏味期》\n威尼斯电影节金狮奖提名作品\n弗朗索瓦·欧容导演作品\n法/英/意语中英双字\n见平👇",
    "《一切顺利》\n苏菲·玛索主演 弗朗索瓦·欧容导演作品\n戛纳电影节金棕榈奖提名作品\n法/德/英语中字\n见平👇",
    "《四万万人民》\n高分历史纪录片推荐\n英/粤语中字\n见平👇",
    "《妮莉和讷亭》\n柏林电影节泰迪熊奖评审团奖获奖作品\n瑞典/德语中英双字\n见平👇",
    "《泥人哥连出世记》\n德国表现主义电影代表作\n默片 中文字幕\n见平👇",
]

for text in test_cases:
    for sub_pat in SUBTITLE_PATTERNS:
        sub_idx = text.find(sub_pat)
        if sub_idx != -1:
            before = text[:sub_idx].rstrip()
            original_before = before
            for old, new in sorted(SLASH_REPLACEMENTS.items(), key=lambda x: len(x[0]), reverse=True):
                before = before.replace(old, new)
            if '/' in original_before or '、' in original_before:
                lang_part = before.split()[-1] if before.split() else ''
                print(f"case={text[:20]}... lang_part={lang_part!r}, sub={sub_pat!r}")
            else:
                print(f"case={text[:20]}... no slash")
            break
