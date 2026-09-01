# -*- coding: utf-8 -*-
"""
微博网络请求层
"""

import json
import logging
import os
import random
import re
import time
from typing import Dict, List, Optional, Set

import requests

import quark
from config import (
    ANTI_BOT_DELAY_MAX,
    ANTI_BOT_DELAY_MIN,
    API_BUILD_COMMENTS,
    API_CONTAINER_TIMELINE,
    API_MYM_BLOG,
    DEFAULT_COMMENT_MAX_PAGES,
    DEFAULT_CONFIG_FILE,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SHORTLINK_TIMEOUT,
    MAX_RETRIES,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    RETRY_BACKOFF_MAX,
    RETRY_BACKOFF_MIN,
    USER_AGENTS,
    WEIBO_HOME_URL,
    WEIBO_REFERER,
)

logger = logging.getLogger(__name__)

COOKIE_RENEWAL_INSTRUCTIONS = """\
Cookie 已失效（ok=-100），请按以下步骤重新获取并更新 config.json：
  1. 用浏览器登录微博网页版（https://weibo.com）。
  2. 进入拓木映画主页 https://weibo.com/u/7608233324。
  3. 打开浏览器开发者工具（F12）→ Network → 刷新页面。
  4. 找一个请求（如 mymblog 或 statuses 开头的），复制 Request Headers 里的完整 Cookie 字段。
  5. 替换 D:\\lobster\\config.json 里的 weibo_cookie 值。
  6. 重新运行程序。"""


class WeiboCrawler:
    """微博爬虫 HTTP 会话与数据获取。"""

    def __init__(
        self,
        uid: str,
        cookie: str,
        user_agents: Optional[List[str]] = None,
        quark_cookie: str = "",
    ) -> None:
        self.session = requests.Session()
        self.uid = uid
        self.cookie = cookie or ""
        self.user_agents = user_agents or USER_AGENTS
        self.processed_ids: Set[str] = set()
        self.quark_client = quark.QuarkClient(quark_cookie or "")

        self._init_session()

    @classmethod
    def from_config_file(
        cls,
        config_path: str = DEFAULT_CONFIG_FILE,
        uid: Optional[str] = None,
    ) -> "WeiboCrawler":
        """从配置文件加载 Cookie 并实例化爬虫。"""
        cookie = ""
        quark_cookie = ""
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                cookie = config.get("weibo_cookie", "")
                quark_cookie = config.get("quark_cookie", "")
                logger.info(f"Cookie 加载成功，长度: {len(cookie)}")
            except Exception as e:
                logger.error(f"加载 Cookie 失败: {e}")
        else:
            logger.warning(f"配置文件不存在: {config_path}")
        return cls(uid=uid or "", cookie=cookie, quark_cookie=quark_cookie)

    def _init_session(self) -> None:
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": WEIBO_REFERER.format(uid=self.uid),
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
        }

        xsrf_match = re.search(r'XSRF-TOKEN=([^;]+)', self.cookie)
        if xsrf_match:
            headers["X-XSRF-TOKEN"] = xsrf_match.group(1)
            logger.debug(f"XSRF-TOKEN: {xsrf_match.group(1)[:20]}...")

        if self.cookie:
            headers["Cookie"] = self.cookie

        self.session.headers.update(headers)

        logger.debug("初始化会话，访问微博主页...")
        self._safe_request("GET", WEIBO_HOME_URL.format(uid=self.uid))

    def _safe_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Optional[requests.Response]:
        """带重试与退避的安全请求。"""
        timeout = kwargs.pop("timeout", DEFAULT_REQUEST_TIMEOUT)
        for attempt in range(MAX_RETRIES):
            try:
                delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                logger.debug(f"等待 {delay:.1f} 秒后请求...")
                time.sleep(delay)

                self.session.headers["User-Agent"] = random.choice(self.user_agents)

                response = self.session.request(method, url, timeout=timeout, **kwargs)

                if response.status_code == 200:
                    return response
                elif response.status_code == 418:
                    logger.warning("触发反爬机制，延长等待...")
                    time.sleep(random.uniform(ANTI_BOT_DELAY_MIN, ANTI_BOT_DELAY_MAX))
                else:
                    logger.warning(f"请求失败: {response.status_code}")

            except Exception as e:
                logger.error(f"请求异常: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(random.uniform(RETRY_BACKOFF_MIN, RETRY_BACKOFF_MAX))

        return None

    def expand_short_link(self, short_url: str) -> Optional[str]:
        """展开微博短链获取真实 URL，纳入重试体系。"""
        if not short_url:
            return None

        response = self._safe_request(
            "HEAD",
            short_url,
            allow_redirects=True,
            timeout=DEFAULT_SHORTLINK_TIMEOUT,
        )
        if response is not None and response.status_code == 200:
            real_url = response.url
            if real_url == short_url:
                # t.cn 限流时返回 200 中间页而非 302 跳转，
                # 改用 GET 抓取页面并解析其中给出的目标链接
                logger.debug(f"短链未跳转，GET 解析中间页: {short_url}")
                page = self._safe_request(
                    "GET",
                    short_url,
                    allow_redirects=True,
                    timeout=DEFAULT_SHORTLINK_TIMEOUT,
                )
                if page is not None and page.status_code == 200:
                    if page.url != short_url:
                        real_url = page.url
                    else:
                        match = re.search(
                            r'(?:url=|href=["\'])(https?://[^"\'<>\s]+)',
                            page.text,
                        )
                        if match and match.group(1) != short_url:
                            real_url = match.group(1)
            logger.debug(f"短链展开: {short_url} -> {real_url}")
            return real_url

        return None

    def load_processed_ids(self, path: str = "processed_weibo.json") -> Set[str]:
        """加载已处理微博 ID 集合。"""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.processed_ids = set(str(x) for x in data)
            except Exception as e:
                logger.error(f"加载已处理 ID 失败: {e}")
                self.processed_ids = set()
        else:
            self.processed_ids = set()
        return self.processed_ids

    def save_processed_ids(self, path: str = "processed_weibo.json") -> None:
        """保存已处理微博 ID 集合。"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sorted(self.processed_ids), f, ensure_ascii=False, indent=2)
            logger.debug(f"已处理 ID 已保存: {path}")
        except Exception as e:
            logger.error(f"保存已处理 ID 失败: {e}")

    def add_processed_id(self, weibo_id: str) -> None:
        """在内存中添加已处理 ID（不自动持久化）。"""
        self.processed_ids.add(str(weibo_id))

    def get_weibo_list(self, page: int = 1) -> List[Dict]:
        """获取微博列表，双 API 回退。"""
        apis = [
            (API_MYM_BLOG, {"uid": self.uid, "page": page, "feature": 0}),
            (API_CONTAINER_TIMELINE, {"containerid": f"107603{self.uid}", "page": page}),
        ]

        for url, params in apis:
            logger.debug(f"尝试接口: {url}")
            response = self._safe_request("GET", url, params=params)

            if not response:
                continue

            try:
                raw_text = response.text[:2000]
                logger.debug(f"原始响应: {raw_text[:500]}...")
            except Exception:
                pass

            try:
                data = response.json()
                logger.debug(f"响应: ok={data.get('ok')}")

                if data.get("ok") == 1:
                    if "data" in data and "list" in data["data"]:
                        weibo_list = data["data"]["list"]
                    elif "data" in data:
                        weibo_list = data.get("data", [])
                    else:
                        weibo_list = []

                    logger.info(f"获取到 {len(weibo_list)} 条微博")
                    for i, w in enumerate(weibo_list[:3]):
                        text = w.get("text", "")
                        text = re.sub(r'<[^>]+>', '', text)
                        logger.debug(f"  微博 {i}: ID={w.get('id')}, 内容={text[:50]}...")

                    return weibo_list
                elif data.get("ok") == -100:
                    logger.error(COOKIE_RENEWAL_INSTRUCTIONS)
                    break
                else:
                    logger.warning(f"接口返回失败: {data.get('msg')}")
            except Exception as e:
                logger.error(f"解析失败: {e}")

        return []

    def extract_image_urls(self, weibo: Dict) -> List[str]:
        """从微博数据中提取图片 URL 列表。"""
        urls = []

        # 新版 API 的 pic_ids + pic_infos
        pic_ids = weibo.get("pic_ids", [])
        pic_infos = weibo.get("pic_infos", {})
        for pid in pic_ids:
            info = pic_infos.get(pid, {})
            for key in ("original", "large", "mw2000", "bmiddle", "orj360"):
                if key in info and isinstance(info[key], dict) and "url" in info[key]:
                    urls.append(info[key]["url"])
                    break

        # 旧版 pics 列表
        for pic in weibo.get("pics", []):
            if not isinstance(pic, dict):
                continue
            url = pic.get("url") or pic.get("large", {}).get("url")
            if url:
                urls.append(url)

        # 视频/卡片封面图
        page_info = weibo.get("page_info", {})
        if isinstance(page_info, dict):
            page_pic = page_info.get("page_pic", {})
            if isinstance(page_pic, dict) and "url" in page_pic:
                urls.append(page_pic["url"])

        return list(dict.fromkeys(urls))

    def get_comments(self, weibo_id: str, max_pages: int = DEFAULT_COMMENT_MAX_PAGES) -> List[Dict]:
        """获取评论（PC 端 API）：时间流 flow=0 为主，无夸克链接时回退热门流 flow=1。

        部分微博的链接评论只出现在热门流（月色撩人：正文与时间流均无链接，
        作者把插了防审查干扰字的夸克链接回复在了热门流里）。
        """
        all_comments = self._fetch_comments_flow(weibo_id, max_pages, flow=0)
        if any(c.get("_quark_link") for c in all_comments):
            return all_comments

        hot_comments = self._fetch_comments_flow(weibo_id, max_pages, flow=1)
        seen = {str(c.get("id") or c.get("mid") or "") for c in all_comments}
        for c in hot_comments:
            key = str(c.get("id") or c.get("mid") or "")
            if key and key not in seen:
                all_comments.append(c)
                seen.add(key)
        return all_comments

    def _fetch_comments_flow(
        self, weibo_id: str, max_pages: int, flow: int
    ) -> List[Dict]:
        """按指定流（0=时间流 1=热门流）拉取评论，支持分页。"""
        all_comments: List[Dict] = []
        max_id = 0
        max_id_type = 0

        for page in range(max_pages):
            url = API_BUILD_COMMENTS
            params: Dict[str, object] = {
                "flow": flow,
                "is_reload": 1,
                "id": weibo_id,
                "is_show_bulletin": 2,
                "is_mix": 0,
                "count": 20,
            }
            if page > 0:
                params["max_id"] = max_id
                params["max_id_type"] = max_id_type

            logger.debug(f"获取评论第 {page + 1} 页，max_id={max_id}")
            response = self._safe_request("GET", url, params=params)
            if not response:
                break

            try:
                data = response.json()
                if data.get("ok") == -100:
                    logger.error(COOKIE_RENEWAL_INSTRUCTIONS)
                    break
                if data.get("ok") != 1:
                    logger.warning(f"获取评论失败: {data.get('msg')}")
                    break

                comments = data.get("data", [])
                if not comments:
                    logger.debug("本页无评论，结束分页")
                    break

                self._enrich_comments(comments)
                all_comments.extend(comments)

                # 获取下一页分页参数
                next_max_id = data.get("max_id", 0)
                next_max_id_type = data.get("max_id_type", 0)
                if not next_max_id or str(next_max_id) == "0":
                    logger.debug("评论已到底，结束分页")
                    break
                max_id = next_max_id
                max_id_type = next_max_id_type

            except Exception as e:
                logger.error(f"解析评论失败: {e}")
                break

        return all_comments

    def _enrich_comments(self, comments: List[Dict]) -> None:
        """从评论结构化数据中提取夸克链接。"""
        quark.enrich_comments(comments)

    def extract_quark_links(self, text: str) -> List[str]:
        """从文本中提取夸克网盘链接。"""
        return quark.extract_quark_links_with_expansion(text, self.expand_short_link)
