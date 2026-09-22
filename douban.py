# -*- coding: utf-8 -*-
"""
豆瓣电影搜索工具

根据中文电影名搜索豆瓣，提取外文名与评分。
"""

import json
import logging
import re
import time
import unicodedata
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

# 连续请求间隔（秒），降低被豆瓣限流概率。
# rexxar 流程每条影片发 2 个请求（搜索 + 详情），取 2 秒维持原单请求节奏
REQUEST_DELAY_SECONDS = 2.0
_last_request_time: float = 0.0

# m.douban.com 会话：复用连接并携带 bid 设备标识 Cookie。
# 匿名无 Cookie 连续请求会被判 need_login（403），带 bid 后正常
_session: Optional["requests.Session"] = None


def _get_session() -> "requests.Session":
    """懒初始化 m.douban.com 会话（先访问首页获取 bid Cookie）。"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://m.douban.com/",
        })
        try:
            _session.get("https://m.douban.com/", timeout=15)
        except requests.RequestException as e:
            logger.warning(f"m.douban.com 会话初始化失败: {e}")
    return _session


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


def _throttled_get(
    url: str, headers: dict, timeout: int = 15, params: Optional[dict] = None,
) -> Optional["requests.Response"]:
    """带请求间隔的会话 GET，失败返回 None。"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)
    _last_request_time = time.time()
    try:
        return _get_session().get(url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as e:
        logger.warning(f"请求失败 {url}: {e}")
        return None


def _fetch_movie_detail(sid: str) -> Optional[dict]:
    """查询条目详情（original_title / aka），失败返回 None。

    通过 m.douban.com 的 rexxar API 获取（详情页有反爬，API 更稳定）。
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
        return response.json()
    except ValueError:
        return None


def _pick_latin_aka(aka_list: Optional[list]) -> Optional[str]:
    """从“又名”列表返回第一个纯拉丁字母标题，无则返回 None。"""
    for aka in aka_list or []:
        if isinstance(aka, str) and _is_latin_title(aka.strip()):
            return aka.strip()
    return None


def _clean_series_suffix(name: str) -> str:
    """截断日文名中常见的“・第X部・...”系列后缀。"""
    name = re.sub(r'[・]\s*第[一二两三四五六七八九十\d]+部[・].*$', '', name)
    name = re.sub(r'[・]\s*第[一二两三四五六七八九十\d]+部.*$', '', name)
    return name.strip()


def _choose_entry(
    entries: List[Tuple[str, Optional[str], Optional[int], Optional[str], str]],
    chinese_name: str,
    year: Optional[int] = None,
    hint_names: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从 (中文标题, 评分, 年份, 条目ID, 块文本) 候选条目中选择最合适的一个，
    返回 (标题, 评分, 条目ID)。

    规则：
    1. 已知年份时，优先在年份匹配的条目中选择。
    2. 提供了主演/导演名时，优先选条目摘要里含这些人名的候选——
       豆瓣按相关性排序可能把同年同名的另一部片排在前
       （“合唱团”：陈意涵《阳光女子合唱团》排在拉尔夫·费因斯 The Choral 前）。
    3. 取相关性排名最靠前的候选——豆瓣搜索排序即为相关性。
       （旧 www/search 流程候选槽位是外文名、需剔除与中文名相同的候选；
       rexxar API 候选即中文标题，精确匹配恰是最相关条目，不再剔除。）
    """
    if not entries:
        return None, None, None

    filtered = list(range(len(entries)))

    if year:
        year_hits = [i for i in filtered if entries[i][2] == year]
        if year_hits:
            filtered = year_hits

    hints = [h.strip() for h in (hint_names or []) if h and h.strip()]
    if hints:
        hint_hits = [
            i for i in filtered
            if any(h in entries[i][4] for h in hints)
        ]
        if hint_hits:
            filtered = hint_hits

    for idx in filtered:
        name = _clean_series_suffix(entries[idx][0])
        if name:
            return name, entries[idx][1], entries[idx][3]
    return None, None, None


def _detail_has_hints(detail: dict, hints: List[str]) -> bool:
    """详情里的导演/演员/摘要文本是否包含任一人名提示。"""
    names = " ".join(
        p.get("name", "") for p in (detail.get("directors") or []) + (detail.get("actors") or [])
    )
    text = f"{names} {detail.get('card_subtitle') or ''}"
    return any(h in text for h in hints)


def _fetch_douban_search(
    chinese_name: str,
    year: Optional[int] = None,
    hint_names: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """请求豆瓣搜索并解析外文名与评分。year 用于歧义中文名的条目筛选，
    hint_names（主演/导演名）用于同名条目的人名甄别。

    主路：m.douban.com 的 rexxar 搜索 API（PC 站 www/search 已对脚本
    软封：连接后不响应/503）；被限流（403 need_login）时自动降级到
    movie.douban.com 的 suggest 建议接口发现条目。"""
    if not chinese_name:
        return None, None

    result = _fetch_via_rexxar_search(chinese_name, year, hint_names)
    if result != (None, None):
        return result
    return _fetch_via_suggest(chinese_name, year, hint_names)


# rexxar 搜索连续 403 后置位：本次进程内跳过主路，直接走 suggest 兜底，
# 避免每条影片都重复探测（每条约 10 秒超时/重试开销）
_rexxar_search_blocked = False


def _fetch_via_rexxar_search(
    chinese_name: str,
    year: Optional[int] = None,
    hint_names: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """rexxar 搜索 API 主路：搜索候选 → 选中条目 → 详情取 original_title。"""
    global _last_request_time, _session, _rexxar_search_blocked
    if _rexxar_search_blocked:
        return None, None
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)

    url = "https://m.douban.com/rexxar/api/v2/search/movie"
    params = {"q": chinese_name}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://m.douban.com/",
    }

    try:
        # 瞬时失败（超时/限流/会话失效）重试一次，避免整条外文名/评分丢失
        response = None
        for attempt in range(2):
            _last_request_time = time.time()
            try:
                response = _get_session().get(
                    url, params=params, headers=headers, timeout=15
                )
                if response.status_code == 403 and attempt == 0:
                    # 会话被判定 need_login，丢弃重建后重试
                    logger.warning("豆瓣搜索 403，重建会话后重试")
                    _session = None
                    time.sleep(3)
                    continue
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
            if response.status_code == 403:
                # 会话重建后仍 403：主路被限流，本进程后续直接走 suggest 兜底
                _rexxar_search_blocked = True
            return None, None

        try:
            data = response.json()
        except ValueError:
            logger.warning("豆瓣搜索返回非 JSON")
            return None, None

        # 条目元组：(中文标题, 评分, 年份, 条目ID, 摘要文本)。
        # card_subtitle 含国家/类型/导演/主演名，供同名条目的人名甄别；
        # 年份是干净字段，无需旧 HTML 解析的防误判处理
        entries: List[Tuple[str, Optional[str], Optional[int], Optional[str], str]] = []
        for item in data.get("items") or []:
            target = item.get("target") or {}
            if not target.get("id"):
                continue
            rating_value = (target.get("rating") or {}).get("value")
            year_str = str(target.get("year") or "")
            entries.append(
                (
                    target.get("title") or "",
                    str(rating_value) if rating_value else None,
                    int(year_str) if year_str.isdigit() else None,
                    str(target["id"]),
                    target.get("card_subtitle") or "",
                )
            )

        if not entries:
            logger.warning(f"豆瓣搜索无结果条目: {chinese_name}")
            return None, None

        _, rating, sid = _choose_entry(entries, chinese_name, year, hint_names)
        # 搜索结果不带外文名，取选中条目详情的 original_title
        foreign_name = None
        detail = _fetch_movie_detail(sid)
        if detail:
            foreign_name = _clean_series_suffix(
                detail.get("original_title") or ""
            ) or None
            # 小语种文字标题（格鲁吉亚文、缅甸文等）改用“又名”中的拉丁字母标题；
            # 中/日/韩/泰/俄等大语种保留原文
            if foreign_name and _is_minor_script(foreign_name):
                latin = _pick_latin_aka(detail.get("aka"))
                if latin:
                    logger.info(f"小语种标题改为拉丁字母: {foreign_name} -> {latin}")
                    foreign_name = latin
        return foreign_name, rating
    except Exception as e:
        logger.error(f"豆瓣搜索异常: {e}")
        return None, None


def _fetch_via_suggest(
    chinese_name: str,
    year: Optional[int] = None,
    hint_names: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """suggest 建议接口兜底：rexxar 搜索被限流时的候选发现。

    movie.douban.com 的建议接口返回条目（sub_title 即外文名，季类条目
    也不带“Season N”后缀），选中后仍取 rexxar 详情补评分/人名甄别。
    """
    response = _throttled_get(
        "https://movie.douban.com/j/subject_suggest",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://movie.douban.com/",
        },
        params={"q": chinese_name},
    )
    if response is None or response.status_code != 200:
        return None, None
    try:
        items = response.json()
    except ValueError:
        return None, None
    if not isinstance(items, list):
        return None, None

    # 建议接口 type 含 book/music 等，只留影视条目（剧集的 type 同为 movie）
    cands = []
    for it in items:
        if it.get("type") != "movie" or not it.get("id"):
            continue
        year_str = str(it.get("year") or "")
        cands.append(
            (
                it.get("title") or "",
                it.get("sub_title") or "",
                int(year_str) if year_str.isdigit() else None,
                str(it["id"]),
            )
        )
    if not cands:
        return None, None

    # 完全同名的条目排前（suggest 相关性可能把季条目排在主条目前）
    cands.sort(key=lambda c: c[0] != chinese_name)

    pool = cands
    if year:
        year_hits = [c for c in pool if c[2] == year]
        if year_hits:
            pool = year_hits

    # 逐个取详情：命中人名提示即选；无提示取第一个有详情的；
    # 全不命中时回退第一个有详情的
    hints = [h.strip() for h in (hint_names or []) if h and h.strip()]
    fallback = None
    for cand in pool[:5]:
        detail = _fetch_movie_detail(cand[3])
        if not detail:
            continue
        if fallback is None:
            fallback = (cand, detail)
        if not hints or _detail_has_hints(detail, hints):
            fallback = (cand, detail)
            break
    if not fallback:
        return None, None
    cand, detail = fallback

    # 外文名优先用 suggest 的 sub_title（季类条目的 original_title 带
    # “Season N”后缀，sub_title 是不带后缀的系列名）
    foreign_name = (
        cand[1]
        or _clean_series_suffix(detail.get("original_title") or "")
        or None
    )
    rating_value = (detail.get("rating") or {}).get("value")
    rating = str(rating_value) if rating_value else None
    if foreign_name and _is_minor_script(foreign_name):
        latin = _pick_latin_aka(detail.get("aka"))
        if latin:
            logger.info(f"小语种标题改为拉丁字母: {foreign_name} -> {latin}")
            foreign_name = latin
    if foreign_name or rating:
        logger.info(f"suggest 兜底命中: {chinese_name} -> {foreign_name} {rating}")
    return foreign_name, rating


def _drop_embedded_name(
    chinese_name: str, foreign_name: Optional[str]
) -> Optional[str]:
    """外文名已包含在中文名里时返回 None（忽略空格与斜杠差异）。

    如“19/20 成年初体验”的豆瓣外文名“19/20”就是片名自带的数字部分，
    再追加会造成重复。
    """
    if not foreign_name:
        return foreign_name
    norm = lambda s: re.sub(r"[\s/／]", "", s or "")
    norm_foreign = norm(foreign_name)
    if norm_foreign and norm_foreign in norm(chinese_name):
        return None
    return foreign_name


def search_movie(
    chinese_name: str,
    year: Optional[int] = None,
    hint_names: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """搜索豆瓣，返回 (外文名, 评分)。year 用于歧义中文名的条目筛选，
    hint_names（主演/导演名）用于同名条目的人名甄别。

    若外文名为中文且与输入完全一致，则外文名返回 None。
    """
    if not chinese_name:
        return None, None

    key = chinese_name.strip()
    hints = [h.strip() for h in (hint_names or []) if h and h.strip()]
    # 缓存照常读取（带 hints 的结果会回写缓存，供后续无 hints 调用复用）；
    # 历史上按旧规则误选的条目靠 TTL 过期后重查升级
    cached = _get_from_cache(key)
    if cached is not None:
        # 旧缓存里可能存着小语种文字标题（拉丁优先规则生效前写入），
        # 视为未命中重查，以便升级为拉丁字母标题并回写缓存
        if not _is_minor_script(cached[0] or ""):
            return _drop_embedded_name(key, cached[0]), cached[1]

    foreign_name, rating = _fetch_douban_search(key, year, hints)

    if foreign_name:
        # 忽略与原名完全一致的中文名
        if _is_chinese(foreign_name) and foreign_name == key:
            foreign_name = None
        else:
            foreign_name = _drop_embedded_name(key, foreign_name)

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
