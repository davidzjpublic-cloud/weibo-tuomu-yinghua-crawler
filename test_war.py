# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from extractor import MovieExtractor

extractor = MovieExtractor()

text = "《战争与人》\n山本萨夫导演高分电影作品\n全3部 日语中日双字\n见平👇"
info = extractor.extract(text)
print(f"director={info.director!r}")
print(f"language={info.language!r}")
print(f"subtitle={info.subtitle!r}")
print(f"season_extra={info.season_extra!r}")
print(f"genre={info.genre!r}")
print(f"rating={info.rating!r}")
