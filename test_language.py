# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from extractor import MovieExtractor

extractor = MovieExtractor()

test_cases = [
    "《爱情赏味期》\n威尼斯电影节金狮奖提名作品\n弗朗索瓦·欧容导演作品\n法/英/意语中英双字\n见平👇",
    "《一切顺利》\n苏菲·玛索主演 弗朗索瓦·欧容导演作品\n戛纳电影节金棕榈奖提名作品\n法/德/英语中字\n见平👇",
    "《四万万人民》\n高分历史纪录片推荐\n英/粤语中字\n见平👇",
    "《妮莉和讷亭》\n柏林电影节泰迪熊奖评审团奖获奖作品\n瑞典/德语中英双字\n见平👇",
    "《泥人哥连出世记》\n德国表现主义电影代表作\n默片 中文字幕\n见平👇",
]

for text in test_cases:
    info = extractor.extract(text)
    print(f"文本: {text[:50]}...")
    print(f"  language={info.language!r}, subtitle={info.subtitle!r}")
    print()
