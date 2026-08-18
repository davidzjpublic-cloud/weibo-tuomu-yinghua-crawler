# -*- coding: utf-8 -*-
import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://m.douban.com/",
}

urls = [
    ("https://m.douban.com/search/", {"type": "1002", "query": "夜空"}),
    ("https://m.douban.com/search/", {"type": "movie", "query": "夜空"}),
]

for url, params in urls:
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"URL: {resp.url}, status={resp.status_code}")
    print("title matches:", re.findall(r'title="([^"]+)"', resp.text)[:5])
    print("rating matches:", re.findall(r'([\d.]+)\s*分', resp.text)[:3])
    print("-" * 60)
