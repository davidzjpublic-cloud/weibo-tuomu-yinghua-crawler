# -*- coding: utf-8 -*-
"""
使用当前 extractor / models / douban 代码，从 results_2026-08-16.json 的原始文本
重新生成 filenames，并与 filenames_2026-08-16_0.txt 基准比较。

若豆瓣搜索失败（如 403），则使用 results_2026-08-16.json 中已保存的
foreign_name 和 douban_rating 作为 fallback，以验证非豆瓣部分的逻辑。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor import MovieExtractor
from models import MovieInfo
from douban import search_movie
from quark import parse_share_file_name


def build_filename(
    raw_text: str,
    quark_file_name: str,
    fallback_foreign_name: str = None,
    fallback_douban_rating: str = None,
) -> str:
    """用当前代码从单条微博文本生成文件名。"""
    extractor = MovieExtractor()
    info = extractor.extract(raw_text)
    if info is None:
        return "[非影视内容]"

    parsed = parse_share_file_name(quark_file_name)
    chinese_name = info.chinese_name or parsed.get("chinese_name")
    # 与 main.py 一致：夸克文件名末尾年份优先
    year = parsed.get("year") or info.year
    file_douban_rating = parsed.get("douban_rating")

    foreign_name = None
    douban_rating_from_search = None
    if chinese_name:
        # 与 main.py 一致：主演/导演名用于豆瓣同名条目甄别
        hint_names = list(info.cast or [])
        if info.director:
            hint_names.append(info.director)
        foreign_name, douban_rating_from_search = search_movie(
            chinese_name, year, hint_names
        )

    if not foreign_name and not douban_rating_from_search:
        # 仅当豆瓣搜索完全失败（外文名、评分均未取到）时才回填保存的外文名；
        # 搜索成功但外文名因已包含在中文名里被去除时不再回填
        foreign_name = fallback_foreign_name
    if not douban_rating_from_search and fallback_douban_rating:
        douban_rating_from_search = fallback_douban_rating

    douban_rating = file_douban_rating or douban_rating_from_search
    if douban_rating:
        rating_match = re.match(r'^(\d+(?:\.\d+)?)$', str(douban_rating).strip())
        if rating_match:
            douban_rating = f"豆瓣{float(rating_match.group(1)):.1f}"

    final = MovieInfo(
        chinese_name=chinese_name,
        foreign_name=foreign_name,
        year=year,
        director=info.director,
        supervisor=info.supervisor,
        writer=info.writer,
        cast=info.cast,
        language=info.language,
        subtitle=info.subtitle,
        genre=info.genre,
        category=info.category,
        related_tag=info.related_tag,
        producer_tag=info.producer_tag,
        work_credit=info.work_credit,
        version_credit=info.version_credit,
        rating=info.rating,
        awards=info.awards,
        season=info.season,
        season_raw=info.season_raw,
        season_extra=info.season_extra,
        episodes=info.episodes,
        raw_text=info.raw_text,
        director_pos=info.director_pos,
        supervisor_pos=info.supervisor_pos,
        writer_pos=info.writer_pos,
        cast_pos=info.cast_pos,
    )
    final.douban_rating = douban_rating
    return final.generate_filename()


def main():
    # 用法: python test_regenerate.py [YYYY-MM-DD] [基准txt路径]
    # 默认重生成 2026-08-16 批次；传日期则读 results_日期.json 对比 filenames_日期_0.txt
    # 基准名与日期不同时可显式指定（如 08-17 批次对比 filenames_2026-08-18_0.txt）
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-08-16"
    json_path = Path(f"output/results_{date}.json")
    baseline_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"output/filenames_{date}_0.txt")
    )
    output_path = Path(f"output/filenames_{date}_regenerated.txt")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for item in data:
        raw_text = item.get("raw_text", "")
        quark_file_name = item.get("quark_file_name", "")
        fallback_foreign = item.get("foreign_name")
        fallback_rating = item.get("douban_rating")
        # 去掉已有的“豆瓣”前缀，方便统一格式化
        if fallback_rating and fallback_rating.startswith("豆瓣"):
            fallback_rating = fallback_rating[2:]
        filename = build_filename(
            raw_text,
            quark_file_name,
            fallback_foreign_name=fallback_foreign,
            fallback_douban_rating=fallback_rating,
        )
        results.append(filename)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, name in enumerate(results, 1):
            f.write(f"{i}. {name}\n")

    print(f"已重新生成: {output_path}")

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_lines = [l.strip() for l in f if l.strip()]

    diff_count = 0
    for i, (actual, expected) in enumerate(zip(results, baseline_lines), 1):
        expected_content = expected.split(". ", 1)[1] if ". " in expected else expected
        if actual != expected_content:
            diff_count += 1
            print(f"第 {i} 行不一致:")
            print(f"  基准: {expected_content}")
            print(f"  实际: {actual}")
            print()

    if len(results) != len(baseline_lines):
        print(f"行数不一致: 基准 {len(baseline_lines)}, 实际 {len(results)}")
    elif diff_count == 0:
        print("✅ 与基准完全一致")
    else:
        print(f"⚠️ 共有 {diff_count} 行不一致")


if __name__ == "__main__":
    main()
