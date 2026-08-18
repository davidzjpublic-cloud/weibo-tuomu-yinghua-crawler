# -*- coding: utf-8 -*-
import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://movie.douban.com/",
}

urls = [
    ("https://search.douban.com/movie/subject_search", {"search_text": "夜空"}),
    ("https://movie.douban.com/j/subject_suggest", {"q": "夜空"}),
]

for url, params in urls:
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"URL: {url}, status={resp.status_code}")
    print(resp.text[:800])
    print("-" * 60)
