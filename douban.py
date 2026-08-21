# -*- coding: utf-8 -*-
"""
豆瓣电影搜索工具

根据中文电影名搜索豆瓣，提取外文名与评分。
"""

import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# 简单内存缓存，避免同一进程内重复请求豆瓣
_cache: dict = {}
# 缓存有效期：评分/外文名极少变化，7 天足够，也避免每天跑一次时缓存全部过期
CACHE_TTL_SECONDS = 7 * 24 * 3600

# 豆瓣本地文件缓存路径（项目根目录）
CACHE_FILE = Path(__file__).resolve().parent / ".douban_cache.json"

# 连续请求间隔（秒），降低被豆瓣限流概率
REQUEST_DELAY_SECONDS = 1.0
_last_request_time: float = 0.0


def _load_disk_cache() -> None:
    """从磁盘加载豆瓣缓存到内存。"""
    global _cache
    if not CACHE_FILE.exists():
        return
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = time.time()
        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            timestamp = entry.get("timestamp", 0)
            if now - timestamp <= CACHE_TTL_SECONDS:
                _cache[key] = (
                    (entry.get("foreign_name"), entry.get("rating")),
                    timestamp,
                )
        logger.info(f"豆瓣磁盘缓存加载完成，共 {len(_cache)} 条")
    except Exception as e:
        logger.warning(f"加载豆瓣缓存失败: {e}")


def _save_disk_cache() -> None:
    """将内存缓存持久化到磁盘。"""
    try:
        data = {}
        for key, (value, timestamp) in _cache.items():
            foreign_name, rating = value
            data[key] = {
                "foreign_name": foreign_name,
                "rating": rating,
                "timestamp": timestamp,
            }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存豆瓣缓存失败: {e}")


def _get_from_cache(key: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
    """从缓存取结果，超时或历史失败结果返回 None。"""
    entry = _cache.get(key)
    if entry is None:
        return None
    value, timestamp = entry
    if time.time() - timestamp > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    # 全空结果视为未命中（可能是当时被限流/解析失败），强制重新查询
    if value == (None, None):
        _cache.pop(key, None)
        return None
    return value


def _set_cache(key: str, value: Tuple[Optional[str], Optional[str]]) -> None:
    """写入缓存并持久化。"""
    _cache[key] = (value, time.time())
    _save_disk_cache()


# 模块导入时加载磁盘缓存
_load_disk_cache()


def _is_chinese(text: str) -> bool:
    """判断字符串是否主要由中文组成。"""
    if not text:
        return False
    return bool(re.search(r'[一-鿿]', text))


# 大语种文字系统：中文/日文（汉字、假名）、韩文、泰文、俄文（西里尔）。
# 这些语言的片名保留原文；其他非拉丁文字（格鲁吉亚文、缅甸文等小语种）
# 自动改用条目“又名”中的拉丁字母标题
_MAJOR_SCRIPTS_PREFIXES = ("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "THAI", "CYRILLIC")


def _char_script_prefix(ch: str) -> str:
    """返回非 ASCII 字符的文字系统前缀（如 GEORGIAN、MYANMAR），无法判断返回空。"""
    try:
        return unicodedata.name(ch).split()[0]
    except ValueError:
        return ""


def _is_minor_script(text: str) -> bool:
    """判断标题是否含小语种文字（非拉丁且不属大语种的字母）。"""
    if not text:
        return False
    for ch in text:
        if ch.isascii() or not ch.isalpha():
            continue
        prefix = _char_script_prefix(ch)
        if not prefix or prefix.startswith("LATIN"):
            continue
        if prefix.startswith(_MAJOR_SCRIPTS_PREFIXES):
            continue
        return True
    return False


def _is_latin_title(text: str) -> bool:
    """判断标题是否为纯拉丁字母（可有变音符号、数字与标点）。"""
    if not text:
        return False
    has_letter = False
    for ch in text:
        if not ch.isalpha():
            continue
        has_letter = True
        if not (ch.isascii() or _char_script_prefix(ch).startswith("LATIN")):
            return False
    return has_letter


def _throttled_get(url: str, headers: dict, timeout: int = 15) -> Optional["requests.Response"]:
    """带请求间隔的 GET，失败返回 None。"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)
    _last_request_time = time.time()
    try:
        return requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        logger.warning(f"请求失败 {url}: {e}")
        return None


def _fetch_latin_aka(sid: str) -> Optional[str]:
    """查询条目“又名”列表，返回第一个纯拉丁字母标题。

    通过 m.douban.com 的 rexxar API 获取（详情页有反爬，API 更稳定）。
    无拉丁标题或请求失败时返回 None（保留原文字标题）。
    """
    if not sid:
        return None
    response = _throttled_get(
        f"https://m.douban.com/rexxar/api/v2/movie/{sid}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://m.douban.com/",
        },
    )
    if response is None or response.status_code != 200:
        return None
    try:
        aka_list = response.json().get("aka") or []
    except ValueError:
        return None
    for aka in aka_list:
        if isinstance(aka, str) and _is_latin_title(aka.strip()):
            return aka.strip()
    return None


def _choose_entry(
    entries: List[Tuple[str, Optional[str], Optional[int], Optional[str]]],
    chinese_name: str,
    year: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从 (标题, 评分, 年份, 条目ID) 候选条目中选择最合适的一个，返回 (外文名, 评分, 条目ID)。

    规则：
    1. 去掉与中文名完全相同的候选（那只是中文名本身，不是外文名）。
    2. 已知年份时，优先在年份匹配的条目中选择。
    3. 取相关性排名最靠前的候选——豆瓣搜索排序即为相关性，
       韩文/日文标题同样是合法外文名，不再按拉丁字母占比跳过。
    4. 清理日文名中常见的“・第X部・...”后缀。
    """
    if not entries:
        return None, None, None

    filtered = [i for i, (t, _, _, _) in enumerate(entries) if t != chinese_name]
    if not filtered:
        filtered = list(range(len(entries)))

    if year:
        year_hits = [i for i in filtered if entries[i][2] == year]
        if year_hits:
            filtered = year_hits

    def clean(n: str) -> str:
        # 截断“・第X部・...”这类日文系列后缀
        n = re.sub(r'[・]\s*第[一二两三四五六七八九十\d]+部[・].*$', '', n)
        n = re.sub(r'[・]\s*第[一二两三四五六七八九十\d]+部.*$', '', n)
        return n.strip()

    for idx in filtered:
        name = clean(entries[idx][0])
        if name:
            return name, entries[idx][1], entries[idx][3]
    return None, None, None


def _fetch_douban_search(
    chinese_name: str, year: Optional[int] = None
) -> Tuple[Optional[str], Optional[str]]:
    """请求豆瓣搜索并解析外文名与评分。year 用于歧义中文名的条目筛选。"""
    if not chinese_name:
        return None, None

    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)

    url = "https://www.douban.com/search"
    params = {"cat": "1002", "q": chinese_name}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.douban.com/",
        "Connection": "keep-alive",
    }

    try:
        # 瞬时失败（超时/限流）重试一次，避免整条外文名/评分丢失
        response = None
        for attempt in range(2):
            _last_request_time = time.time()
            try:
                response = requests.get(url, params=params, headers=headers, timeout=15)
                break
            except requests.RequestException as e:
                if attempt == 0:
                    logger.warning(f"豆瓣搜索请求异常，3 秒后重试: {e}")
                    time.sleep(3)
        if response is None:
            logger.error(f"豆瓣搜索重试后仍失败: {chinese_name}")
            return None, None
        if response.status_code != 200:
            logger.warning(f"豆瓣搜索请求失败: {response.status_code}")
            return None, None

        text = response.text

        # 按搜索结果块配对解析（标题 + 该条目自己的评分 + 条目年份 + 条目ID），
        # 避免外文名取自候选 A 而评分取自页面第一个结果
        entries: List[Tuple[str, Optional[str], Optional[int], Optional[str]]] = []
        for block in re.split(r'<div[^>]*class="[^"]*result[^"]*"', text)[1:]:
            title_match = re.search(
                r'<a[^>]*class="nbg"[^>]*title="([^"]+)"', block,
            )
            if not title_match:
                continue
            # 条目ID：onclick 里的 sid 或 link2 跳转 URL 中编码的 subject id
            sid_match = re.search(r'sid:\s*(\d+)', block)
            if not sid_match:
                sid_match = re.search(r'subject%2F(\d+)', block)
            rating_match = re.search(
                r'<span[^>]*class="rating_nums"[^>]*>([\d.]+)</span>',
                block,
            )
            # 条目年份取标题属性以外的第一个四位数年份（信息行里的上映年）。
            # 先剥掉 HTML 标签/属性（海报 URL “p1197911950.jpg”、条目链接
            # “subject/1999147”里的数字会被当年份），再剔除“N人评（价）”
            # 的评价人数（否则“（1979人评价）”会被当成 1979 年），
            # 并跳过超出合理区间的数字（摘要里的年份/编号等）
            block_wo_title = re.sub(
                r'<a[^>]*class="nbg"[^>]*title="[^"]*"', '', block,
            )
            plain_block = re.sub(r'<[^>]+>', ' ', block_wo_title)
            plain_block = re.sub(r'\d+人评价?', ' ', plain_block)
            max_year = datetime.now().year + 3
            year_match = None
            for m in re.finditer(r'(19|20)\d{2}', plain_block):
                y = int(m.group(0))
                if 1900 <= y <= max_year:
                    year_match = m
                    break
            entries.append(
                (
                    title_match.group(1),
                    rating_match.group(1) if rating_match else None,
                    int(year_match.group(0)) if year_match else None,
                    sid_match.group(1) if sid_match else None,
                )
            )

        if not entries:
            logger.warning(f"豆瓣搜索无结果条目: {chinese_name}")
            return None, None

        foreign_name, rating, sid = _choose_entry(entries, chinese_name, year)
        # 小语种文字标题（格鲁吉亚文、缅甸文等）改用“又名”中的拉丁字母标题；
        # 中/日/韩/泰/俄等大语种保留原文
        if foreign_name and _is_minor_script(foreign_name):
            latin = _fetch_latin_aka(sid)
            if latin:
                logger.info(f"小语种标题改为拉丁字母: {foreign_name} -> {latin}")
                foreign_name = latin
        return foreign_name, rating
    except Exception as e:
        logger.error(f"豆瓣搜索异常: {e}")
        return None, None


def search_movie(
    chinese_name: str, year: Optional[int] = None
) -> Tuple[Optional[str], Optional[str]]:
    """搜索豆瓣，返回 (外文名, 评分)。year 用于歧义中文名的条目筛选。

    若外文名为中文且与输入完全一致，则外文名返回 None。
    """
    if not chinese_name:
        return None, None

    key = chinese_name.strip()
    cached = _get_from_cache(key)
    if cached is not None:
        # 旧缓存里可能存着小语种文字标题（拉丁优先规则生效前写入），
        # 视为未命中重查，以便升级为拉丁字母标题并回写缓存
        if not _is_minor_script(cached[0] or ""):
            return cached

    foreign_name, rating = _fetch_douban_search(key, year)

    if foreign_name:
        # 忽略与原名完全一致的中文名
        if _is_chinese(foreign_name) and foreign_name == key:
            foreign_name = None

    result = (foreign_name, rating)
    # 仅缓存成功结果：被限流/解析失败返回的 (None, None) 不固化到缓存
    if foreign_name or rating:
        _set_cache(key, result)
    return result


def search_movie_foreign_name(chinese_name: str) -> Optional[str]:
    """仅获取外文名。"""
    foreign_name, _ = search_movie(chinese_name)
    return foreign_name


def search_movie_rating(chinese_name: str) -> Optional[str]:
    """仅获取豆瓣评分。"""
    _, rating = search_movie(chinese_name)
    return rating
