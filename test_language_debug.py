# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SLASH_REPLACEMENTS, LANGUAGE_NAMES, SUBTITLE_PATTERNS

text = "《爱情赏味期》\n威尼斯电影节金狮奖提名作品\n弗朗索瓦·欧容导演作品\n法/英/意语中英双字\n见平👇"

for sub_pat in SUBTITLE_PATTERNS:
    sub_idx = text.find(sub_pat)
    if sub_idx != -1:
        before = text[:sub_idx].rstrip()
        print(f"sub_pat={sub_pat!r}, before={before!r}")
        for old, new in sorted(SLASH_REPLACEMENTS.items(), key=lambda x: len(x[0]), reverse=True):
            if old in before:
                before = before.replace(old, new)
                print(f"  replaced {old!r} -> {new!r}, before={before!r}")
        break

print(f"最终 before={before!r}")

# 模拟从后往前匹配
found_langs = []
temp = before
priority_combo = ['韩日英语', '英白俄罗斯波兰语', '英印地孟加拉法语', '英印地孟加拉语', '法波兰俄语', '乌兹别克俄语']
while temp:
    matched = False
    for combo in priority_combo:
        if temp.endswith(combo):
            found_langs.append(combo)
            temp = temp[:-len(combo)].rstrip()
            if temp.endswith('/') or temp.endswith('、'):
                temp = temp[:-1].rstrip()
            matched = True
            break
    if matched:
        continue
    for lang in sorted(LANGUAGE_NAMES, key=len, reverse=True):
        if temp.endswith(lang):
            found_langs.append(lang)
            temp = temp[:-len(lang)].rstrip()
            if temp.endswith('/') or temp.endswith('、'):
                temp = temp[:-1].rstrip()
            matched = True
            break
    if not matched:
        break
print(f"found_langs={found_langs}")
print(f"reversed={list(reversed(found_langs))}")
print(f"language={''.join(reversed(found_langs))!r}")
