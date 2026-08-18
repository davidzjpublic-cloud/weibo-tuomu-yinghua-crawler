# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from extractor import MovieExtractor

extractor = MovieExtractor()
text = "《操控游戏》\n池昌旭/都敬秀/李光洙主演犯罪剧集\n全12集 韩语中字\n见平👇 ​ ​​​"
info = extractor.extract(text)
print(f"language={info.language!r}")
print(f"subtitle={info.subtitle!r}")
print(f"episodes={info.episodes!r}")
print(f"category={info.category!r}")
print(f"genre={info.genre!r}")
