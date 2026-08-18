# -*- coding: utf-8 -*-
"""
从基准文件名列表和 results JSON 中提取正确的外文名与豆瓣评分，
初始化 douban.py 的本地缓存 .douban_cache.json，用于离线验证。
"""

import json
import re
import time
from pathlib import Path


def parse_baseline(path: Path, results: list):
    """解析基准文件名列表，返回 {中文名: 外文名}。

    按 results 的顺序逐行对应，用中文名截取其后到括号前的内容作为外文名。
    若截取内容仅为季数描述（如 '1-4季'），则视为无外文名。
    """
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    for i, line in enumerate(lines):
        if i >= len(results):
            break
        chinese = results[i].get("chinese_name", "")
        content = line.split(". ", 1)[1] if ". " in line else line
        if not chinese or not content.startswith(chinese):
            mapping[chinese] = None
            continue
        rest = content[len(chinese):].strip()
        foreign = rest.split("（")[0].strip()
        # 仅含季数信息的不是外文名
        if foreign and re.match(r'^[0-9\s\-~～]+季?$', foreign):
            foreign = None
        # 去掉外文名末尾的季节描述（如 "Sister Boniface Mysteries 1-3季"）
        if foreign:
            foreign = re.sub(r'\s+(?:1-\d+|第\d+)季$', '', foreign).strip() or None
        mapping[chinese] = foreign or None
    return mapping


def main():
    baseline_path = Path("filenames_2026-08-16_0.txt")
    results_path = Path("results_2026-08-16.json")
    cache_path = Path(".douban_cache.json")

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    foreign_map = parse_baseline(baseline_path, data)

    cache = {}
    for item in data:
        chinese = item.get("chinese_name")
        if not chinese:
            continue
        foreign = foreign_map.get(chinese)
        rating = item.get("douban_rating")
        if rating and rating.startswith("豆瓣"):
            rating = rating[2:]
        cache[chinese] = {
            "foreign_name": foreign,
            "rating": rating,
            "timestamp": int(time.time()),
        }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"已生成缓存: {cache_path}, 共 {len(cache)} 条")


if __name__ == "__main__":
    main()
