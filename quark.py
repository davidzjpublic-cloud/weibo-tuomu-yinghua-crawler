# -*- coding: utf-8 -*-
"""
夸克网盘相关工具与客户端

职责：
1. 从微博文本/评论中提取夸克网盘共享链接。
2. 调用夸克分享 API 获取网盘内文件列表。
3. 解析网盘文件名，提取电影名、出品年份、豆瓣评分。
"""

import base64
import hashlib
import json
import logging
import mimetypes
import random
import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import requests

from config import LANGUAGE_NAMES, SUBTITLE_PATTERNS
from utils import clean_html

logger = logging.getLogger(__name__)

QUARK_HOST = "pan.quark.cn"
QUARK_SHARE_HOST = "https://drive-m.quark.cn"
QUARK_LINK_PATTERN = r'https?://pan\.quark\.cn/s/[a-zA-Z0-9]+'
QUARK_LINK_KEY = "_quark_link"
SHORT_LINK_KEY = "_short_link"


def is_quark_link(url: Optional[str]) -> bool:
    """判断 URL 是否为夸克网盘链接。"""
    return bool(url) and "quark" in url and "pan.quark.cn" in url


def _strip_link_obfuscation(text: str) -> str:
    """剔除链接中的中文干扰字（博主防审查手法，URL 本身不含中文）。

    如“htt删ps://pan.quar掉k.cn/s/5410a字4d124c4”→“https://pan.quark.cn/s/5410a4d124c4”。
    """
    return re.sub(r'[一-鿿]', '', text)


def extract_quark_links(text: str) -> List[str]:
    """从文本中提取夸克网盘链接（不展开短链）。"""
    if not text:
        return []
    text = _strip_link_obfuscation(text)

    links = []

    # 1. 完整链接
    links.extend(re.findall(QUARK_LINK_PATTERN, text))

    # 2. weibo.cn/sinaurl 编码链接
    sinaurl_pattern = r'https?://weibo\.cn/sinaurl\?u=([^&\s]+)'
    for encoded_url in re.findall(sinaurl_pattern, text):
        decoded = urllib.parse.unquote(encoded_url)
        if is_quark_link(decoded):
            links.append(decoded)

    # 3. 裸 pan.quark.cn/s/xxx
    plain_pattern = r'pan\.quark\.cn/s/([a-zA-Z0-9]+)'
    for pl in re.findall(plain_pattern, text):
        links.append(f"https://pan.quark.cn/s/{pl}")

    return list(dict.fromkeys(links))


def extract_quark_links_with_expansion(
    text: str,
    expander: Callable[[str], Optional[str]],
) -> List[str]:
    """从文本中提取夸克网盘链接，包含 t.cn 短链展开。"""
    text = _strip_link_obfuscation(text)
    links = extract_quark_links(text)

    # 4. t.cn 短链展开
    tcn_pattern = r'https?://t\.cn/[a-zA-Z0-9]+'
    for tcn in re.findall(tcn_pattern, text):
        expanded = expander(tcn)
        if expanded and is_quark_link(expanded):
            links.append(expanded)

    return list(dict.fromkeys(links))


def enrich_comments(comments: List[Dict]) -> None:
    """从评论结构化数据中提取夸克链接和待展开短链。"""
    for comment in comments:
        url_struct = comment.get("url_struct", [])
        for url_item in url_struct:
            short_url = url_item.get("short_url", "")
            long_url = url_item.get("long_url", "")
            if long_url and is_quark_link(long_url):
                comment[QUARK_LINK_KEY] = long_url
                logger.info(f"  从url_struct找到夸克链接: {long_url}")
            elif short_url:
                comment[SHORT_LINK_KEY] = short_url

        topic_struct = comment.get("topic_struct", [])
        for topic in topic_struct:
            topic_url = topic.get("topic_url", "")
            if topic_url and is_quark_link(topic_url):
                comment[QUARK_LINK_KEY] = topic_url

        page_info = comment.get("page_info", {})
        if page_info:
            media_url = page_info.get("media_info", {}).get("stream_url", "")
            if media_url and is_quark_link(media_url):
                comment[QUARK_LINK_KEY] = media_url
            page_url = page_info.get("page_url", "")
            if page_url and is_quark_link(page_url):
                comment[QUARK_LINK_KEY] = page_url


def find_quark_link_in_comments(
    comments: List[Dict],
    expander: Callable[[str], Optional[str]],
) -> Optional[str]:
    """从评论列表中按优先级找出第一个夸克网盘链接。"""
    enrich_comments(comments)

    quark_links = []
    for comment in comments:
        if QUARK_LINK_KEY in comment:
            quark_links.append(comment[QUARK_LINK_KEY])

        if SHORT_LINK_KEY in comment:
            expanded = expander(comment[SHORT_LINK_KEY])
            if expanded and is_quark_link(expanded):
                quark_links.append(expanded)

        comment_text = clean_html(comment.get("text", ""))
        links = extract_quark_links_with_expansion(comment_text, expander)
        quark_links.extend(links)

    deduped = list(dict.fromkeys(quark_links))
    return deduped[0] if deduped else None


def parse_share_file_name(file_name: str) -> Dict[str, Optional[object]]:
    """解析夸克网盘文件名，提取片名、年份、豆瓣评分。

    示例：
        - "贝尔法斯特天堂路2026" -> name="贝尔法斯特天堂路", year=2026, rating=None
        - "盗梦空间2010豆瓣9.3.mkv" -> name="盗梦空间", year=2010, rating="豆瓣9.3"
        - "真凶密码2015中英双字" -> name="真凶密码", year=2015, rating=None
    """
    if not file_name:
        return {"chinese_name": None, "year": None, "douban_rating": None}

    name = file_name.strip()

    # 去掉常见视频扩展名
    name = re.sub(
        r'\.(mkv|mp4|avi|ts|mov|wmv|flv|rmvb|m2ts|iso|mpg|mpeg|m4v|webm|strm)$',
        '',
        name,
        flags=re.IGNORECASE,
    )

    # 提取豆瓣评分
    douban_rating = None
    rating_patterns = [
        r'(?:豆瓣|db)\s*(\d\.\d)',
        r'豆瓣评分\s*(\d\.\d)',
    ]
    for pat in rating_patterns:
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            douban_rating = f"豆瓣{m.group(1)}"
            name = (name[:m.start()] + name[m.end():]).strip()
            break

    # 提取年份：取最后一个 1900-2099 的 4 位数字。
    # 剥离后剩余为空时（如片名本身只有“2012”）不剥离，避免片名被截空
    year = None
    year_matches = list(re.finditer(r'(19|20)\d{2}', name))
    if year_matches:
        last = year_matches[-1]
        remainder = (name[:last.start()] + name[last.end():]).strip()
        if remainder:
            year = int(last.group(0))
            name = remainder

    # 去掉末尾的括号（如 "某片 (2011)")
    name = re.sub(r'\s*[（(]\s*[）)]\s*$', '', name).strip()

    # 去掉常见字幕/语言后缀（只在末尾或独立词出现）
    subtitle_pat = '|'.join(re.sub(r'([.*+?^${}()|[\]\\])', r'\\\1', p) for p in SUBTITLE_PATTERNS)
    name = re.sub(rf'(?:^|[^\w一-鿿])({subtitle_pat})$', '', name).strip()
    # 再去一次可能残留的语言+字幕组合（如 "中英双字" 已处理）
    name = re.sub(rf'({subtitle_pat})$', '', name).strip()

    # 去掉末尾已知语言名（如 "国语"、"英语" 等）
    for lang in sorted(LANGUAGE_NAMES, key=len, reverse=True):
        if name.endswith(lang):
            name = name[:-len(lang)].rstrip()
            break

    # 清理多余分隔符与空格
    name = re.sub(r'[._\-\s]+', ' ', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()

    # 去掉末尾非中文/非季数词的外语尾巴（如 "这不是一部电影 این فیلم نیست"）
    # 保留含中文的片段以及季节数字词
    def _has_cjk_or_season(token: str) -> bool:
        if re.search(r'[一-鿿]', token):
            return True
        # 允许纯阿拉伯数字或中文数字作为季节词的一部分
        if re.fullmatch(r'[一二两三四五六七八九十\d]+季?', token):
            return True
        return False

    tokens = name.split()
    kept = []
    for token in tokens:
        if _has_cjk_or_season(token):
            kept.append(token)
        else:
            # 一旦遇到不含中文/非季节的尾巴片段就停止
            break
    if kept:
        name = ' '.join(kept)

    # 再次清理并归一化冒号
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\s*：\s*', '：', name)

    if not name:
        name = None

    return {
        "chinese_name": name,
        "year": year,
        "douban_rating": douban_rating,
    }


class QuarkClient:
    """夸克网盘客户端：用 cookie 调用夸克分享 API。"""

    def __init__(
        self,
        cookie: str,
        request_delay: Tuple[float, float] = (0.5, 1.5),
    ) -> None:
        self.cookie = cookie or ""
        self.request_delay = request_delay
        self.session = requests.Session()
        self._share_info_cache: Dict[str, Dict] = {}

        # 个人网盘 API 通常需要把 ctoken 作为 query 参数
        ctoken_match = re.search(r'ctoken=([^;]+)', self.cookie)
        self.ctoken = ctoken_match.group(1) if ctoken_match else ""

        if self.cookie:
            self.session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Cookie": self.cookie,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://pan.quark.cn/",
            })

    def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Optional[Dict]:
        """发起夸克 API 请求，返回解析后的 JSON 数据。

        对网络层异常（连接断开、超时）和服务端 5xx 错误自动重试，
        默认最多 3 次，指数退避。
        """
        if not self.cookie:
            logger.warning("Quark cookie 未配置，跳过请求")
            return None

        max_retries = kwargs.pop("retries", 3)
        timeout = kwargs.pop("timeout", 20)
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                delay = random.uniform(*self.request_delay)
                time.sleep(delay)
                response = self.session.request(
                    method, url, timeout=timeout, **kwargs
                )
                if response.status_code == 200:
                    return response.json()
                # 服务端 5xx 可重试
                if response.status_code >= 500 and attempt < max_retries:
                    logger.warning(
                        f"夸克 API 返回 {response.status_code}，"
                        f"{attempt + 1} 秒后重试（{attempt}/{max_retries}）"
                    )
                    time.sleep(attempt * 2)
                    continue
                logger.warning(
                    f"夸克 API 请求失败: {response.status_code} {response.text[:200]}"
                )
                return None
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"夸克 API 请求异常: {e}，"
                        f"{attempt + 1} 秒后重试（{attempt}/{max_retries}）"
                    )
                    time.sleep(attempt * 2)
                    continue
                logger.error(f"夸克 API 请求异常: {e}")

        return None

    @staticmethod
    def _get_pwd_id(share_url: str) -> Optional[str]:
        """从分享链接中解析 pwd_id。"""
        m = re.search(r'pan\.quark\.cn/s/([a-zA-Z0-9]+)', share_url)
        return m.group(1) if m else None

    def _get_share_info(self, pwd_id: str) -> Optional[Dict]:
        """获取分享 token 信息，包含 stoken 和 title，带缓存。"""
        if pwd_id in self._share_info_cache:
            return self._share_info_cache[pwd_id]

        url = f"{QUARK_SHARE_HOST}/1/clouddrive/share/sharepage/token"
        data = self._request(
            "POST",
            url,
            json={"pwd_id": pwd_id, "passcode": ""},
        )
        if data and data.get("code") == 0:
            self._share_info_cache[pwd_id] = data
            return data
        return None

    def _get_stoken(self, pwd_id: str) -> Optional[str]:
        """获取 stoken。"""
        info = self._get_share_info(pwd_id)
        if info:
            return info.get("data", {}).get("stoken")
        return None

    def get_share_title(self, share_url: str) -> Optional[str]:
        """获取分享标题（通常与根文件夹同名）。"""
        pwd_id = self._get_pwd_id(share_url)
        if not pwd_id:
            return None
        info = self._get_share_info(pwd_id)
        if info:
            return info.get("data", {}).get("title")
        return None

    def list_share_files(self, share_url: str) -> List[Dict]:
        """获取分享根目录下的文件/文件夹列表。"""
        pwd_id = self._get_pwd_id(share_url)
        if not pwd_id:
            return []

        stoken = self._get_stoken(pwd_id)
        if not stoken:
            return []

        url = f"{QUARK_SHARE_HOST}/1/clouddrive/share/sharepage/detail"
        params = {
            "pwd_id": pwd_id,
            "stoken": stoken,
            "dirid": "0",
            "page": 1,
            "size": 50,
        }
        data = self._request("GET", url, params=params)
        if data and data.get("code") == 0:
            return data.get("data", {}).get("list", [])
        return []

    def get_first_file_name(self, share_url: str) -> Optional[str]:
        """获取分享中第一个文件/文件夹名；无文件时回退到分享标题。"""
        files = self.list_share_files(share_url)
        if files:
            return files[0].get("file_name")
        return self.get_share_title(share_url)

    def _drive_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Optional[Dict]:
        """调用需要登录态的夸克个人文件 API。

        个人文件 API 通常需要附带 pr=ucpro、fr=pc 等 query 参数。
        """
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs.setdefault("pr", ["ucpro"])
        qs.setdefault("fr", ["pc"])
        new_query = urllib.parse.urlencode(qs, doseq=True)
        url = urllib.parse.urlunparse(parsed._replace(query=new_query))

        return self._request(method, url, **kwargs)

    def list_my_files(
        self,
        pdir_fid: str = "0",
        size: int = 100,
    ) -> List[Dict]:
        """列出自己网盘某目录下的文件/文件夹。"""
        url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/sort"
        params = {
            "pdir_fid": pdir_fid,
            "_page": 1,
            "_size": size,
            "_fetch_total": 1,
            "_fetch_sub_dirs": 0,
            "_sort": "file_name:asc",
        }
        data = self._drive_request("GET", url, params=params)
        if data and data.get("code") == 0:
            return data.get("data", {}).get("list", [])
        return []

    def list_all_my_files(
        self,
        pdir_fid: str = "0",
        size: int = 100,
    ) -> List[Dict]:
        """分页列出目录下全部文件/文件夹。"""
        all_files: List[Dict] = []
        page = 1
        while True:
            url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/sort"
            params = {
                "pdir_fid": pdir_fid,
                "_page": page,
                "_size": size,
                "_fetch_total": 1,
                "_fetch_sub_dirs": 0,
                "_sort": "file_name:asc",
            }
            data = self._drive_request("GET", url, params=params)
            if not data or data.get("code") != 0:
                break
            items = data.get("data", {}).get("list", [])
            if not items:
                break
            all_files.extend(items)
            if len(items) < size:
                break
            page += 1
        return all_files

    def find_or_create_dir(self, path: str) -> Optional[str]:
        """在网盘中查找或创建目录，返回最后一级目录的 fid。

        path 示例："来自：分享/【拓临】"，会拆分为 ["来自：分享", "【拓临】"]。
        """
        if not path:
            return "0"

        parts = [p.strip() for p in path.split("/") if p.strip()]
        if not parts:
            return "0"

        current_fid = "0"
        for part in parts:
            children = self.list_my_files(current_fid, size=200)
            found = None
            for child in children:
                if child.get("file_name") == part and child.get("file_type") == 0:
                    found = child
                    break

            if found:
                current_fid = found["fid"]
                logger.info(f"找到目录: {part} -> fid={current_fid}")
                continue

            # 创建目录
            url = f"{QUARK_SHARE_HOST}/1/clouddrive/file"
            create_data = {
                "pdir_fid": current_fid,
                "file_name": part,
                "dir_path": "",
                "dir_init_lock": False,
            }
            data = self._drive_request(
                "POST",
                url,
                json=create_data,
                headers={"Content-Type": "application/json"},
            )
            if data and data.get("code") == 0:
                current_fid = data.get("data", {}).get("fid")
                logger.info(f"创建目录: {part} -> fid={current_fid}")
            else:
                logger.error(f"创建目录失败: {part}, 响应: {data}")
                return None

        return current_fid

    def _get_share_fid_token_map(
        self,
        pwd_id: str,
        stoken: str,
    ) -> Dict[str, str]:
        """从分享根目录详情中提取每个 fid 对应的 share_fid_token。"""
        url = f"{QUARK_SHARE_HOST}/1/clouddrive/share/sharepage/detail"
        params = {
            "pwd_id": pwd_id,
            "stoken": stoken,
            "dirid": "0",
            "page": 1,
            "size": 50,
        }
        data = self._request("GET", url, params=params)
        if not data or data.get("code") != 0:
            return {}

        token_map: Dict[str, str] = {}
        for item in data.get("data", {}).get("list", []):
            fid = item.get("fid")
            token = item.get("share_fid_token") or item.get("share_fidToken")
            if fid and token:
                token_map[fid] = token
        return token_map

    def _find_saved_by_name(
        self,
        to_dir_fid: str,
        items: List[Dict],
    ) -> Optional[List[Dict]]:
        """在目标目录中按分享原名查找已转存项（转存超时防重复用）。

        转存请求超时但服务端已生效时，目标目录会出现与分享根文件夹同名
        的目录。所有 item 都能按（share_file_name 优先，file_name 兜底）
        找到同名项时返回与 save_share_files 相同结构的结果，否则 None。
        """
        children = self.list_all_my_files(to_dir_fid, size=100)
        results = []
        for item in items:
            expected = item.get("share_file_name") or item.get("file_name")
            if not expected:
                return None
            found = next(
                (
                    c for c in children
                    if c.get("file_name") == expected and c.get("fid")
                ),
                None,
            )
            if not found:
                return None
            results.append({
                "fid": found["fid"],
                "original_fid": item.get("fid"),
                "file_name": item.get("file_name"),
            })
        return results

    def _cleanup_duplicate_saves(
        self,
        to_dir_fid: str,
        items: List[Dict],
        keep_fids: List[str],
    ) -> None:
        """清理转存窗口内遗留的同名重复目录。

        转存 POST 超时但服务端已生效时，重试会产生未改名的同名副本；
        调用方（main.py）转存前已删除目标目录中的同名项，因此这里同名
        且不在 keep_fids 中的目录必然是本次转存窗口的遗留，直接删除。
        """
        expected_names = {
            item.get("share_file_name") or item.get("file_name")
            for item in items
        } - {None, ""}
        if not expected_names:
            return
        children = self.list_all_my_files(to_dir_fid, size=100)
        dup_fids = [
            c["fid"] for c in children
            if c.get("file_name") in expected_names
            and c.get("fid") not in keep_fids
        ]
        if dup_fids:
            names = [c.get("file_name") for c in children if c.get("fid") in dup_fids]
            logger.warning(f"清理超时重试遗留的重复转存: {names}")
            self.delete_files(dup_fids)

    def save_share_files(
        self,
        share_url: str,
        items: List[Dict],
        to_dir_fid: str,
        max_retries: int = 3,
    ) -> List[Dict]:
        """将分享中的指定文件/文件夹保存到自己网盘的指定目录。

        每个 item 至少包含 fid；share_fid_token 缺失时会从分享详情自动补齐。
        对网络超时/token 校验异常会自动重试。
        返回转存后的结果列表，元素包含 saved_fid 与 original_fid / file_name。
        """
        if not items:
            return []

        pwd_id = self._get_pwd_id(share_url)
        stoken = self._get_stoken(pwd_id) if pwd_id else None
        if not pwd_id or not stoken:
            logger.error("无法获取分享 pwd_id 或 stoken，跳过转存")
            return []

        fid_list = [item.get("fid") for item in items if item.get("fid")]
        if not fid_list:
            logger.error("没有有效的分享 fid，跳过转存")
            return []

        url = f"{QUARK_SHARE_HOST}/1/clouddrive/share/sharepage/save"

        for attempt in range(1, max_retries + 1):
            # 每次重试都重新获取 share_fid_token，避免过期
            token_map = self._get_share_fid_token_map(pwd_id, stoken)
            fid_token_list = []
            for item in items:
                fid = item.get("fid")
                if not fid:
                    continue
                token = (
                    item.get("share_fid_token")
                    or item.get("share_fidToken")
                    or token_map.get(fid, "")
                )
                fid_token_list.append(token)

            payload = {
                "fid_list": fid_list,
                "fid_token_list": fid_token_list,
                "to_pdir_fid": to_dir_fid,
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": "0",
                "scene": "link",
                "pdir_save_all": False,
            }
            # 转存 POST 非幂等：禁用 _request 的内层自动重试（retries=1），
            # 由本方法的超时探测逻辑决定是否重发，避免服务端已生效时重复转存
            data = self._drive_request(
                "POST",
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=180,
                retries=1,
            )

            if data and data.get("code") == 0:
                # 同步转存结果在 task_resp.data.save_as.save_as_top_fids
                task_resp = data.get("data", {}).get("task_resp", {})
                save_as = task_resp.get("data", {}).get("save_as", {})
                saved_fids = save_as.get("save_as_top_fids", [])

                # 如果当前未返回结果，则轮询任务状态
                if not saved_fids and data.get("data", {}).get("task_id"):
                    saved_fids = self._wait_save_task(data["data"]["task_id"])

                # 轮询超时但任务可能已在服务端迟完成（排队超轮询窗口）：
                # 按分享原名探测目标目录，找到即复用，避免重发造成重复转存
                if not saved_fids:
                    adopted = self._find_saved_by_name(to_dir_fid, items)
                    if adopted is not None:
                        logger.warning(
                            "转存任务轮询超时但服务端已生效，复用目标目录中已转存项: "
                            + ", ".join(r["fid"] for r in adopted)
                        )
                        self._cleanup_duplicate_saves(
                            to_dir_fid, items, [r["fid"] for r in adopted]
                        )
                        return adopted
                    if attempt < max_retries:
                        logger.warning(
                            f"转存任务轮询未完成（第 {attempt} 次），"
                            f"{attempt * 2} 秒后重新提交"
                        )
                        time.sleep(attempt * 2)
                        continue
                    logger.error("转存任务多次轮询未完成，放弃")
                    return []

                results = []
                for idx, saved_fid in enumerate(saved_fids):
                    original = items[idx] if idx < len(items) else {}
                    results.append({
                        "fid": saved_fid,
                        "original_fid": original.get("fid"),
                        "file_name": original.get("file_name"),
                    })

                logger.info(f"转存成功 {len(results)} 项到 {to_dir_fid}")
                if results:
                    # 早前超时的尝试可能已在服务端生效，留下未改名副本，清掉
                    self._cleanup_duplicate_saves(
                        to_dir_fid, items, [r["fid"] for r in results]
                    )
                return results

            # 网络层失败（读超时等）时请求可能已在服务端生效：
            # 先按分享原名探测目标目录，找到即复用，避免重发造成重复转存
            if data is None:
                adopted = self._find_saved_by_name(to_dir_fid, items)
                if adopted is not None:
                    logger.warning(
                        "转存请求超时但服务端已生效，复用目标目录中已转存项: "
                        + ", ".join(r["fid"] for r in adopted)
                    )
                    self._cleanup_duplicate_saves(
                        to_dir_fid, items, [r["fid"] for r in adopted]
                    )
                    return adopted

            # 判断是否需要重试
            msg = (data or {}).get("message", "")
            is_token_error = "token" in msg.lower() or "校验异常" in msg
            if attempt < max_retries and (is_token_error or data is None):
                logger.warning(
                    f"转存失败（第 {attempt} 次），{attempt + 1} 秒后重试: {msg[:80]}"
                )
                time.sleep(attempt * 2)
                continue

            logger.error(f"转存失败: {data}")
            return []

    def delete_files(
        self,
        fid_list: List[str],
        timeout: int = 60,
    ) -> bool:
        """删除自己网盘中的文件/文件夹，等待异步任务完成。

        Args:
            fid_list: 要删除的 fid 列表。
            timeout: 等待删除完成的最大秒数。

        Returns:
            删除成功返回 True，否则返回 False。
        """
        if not fid_list:
            return True

        url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/delete"
        payload = {
            "action_type": 2,
            "filelist": fid_list,
            "exclude_fids": [],
        }
        data = self._drive_request(
            "POST",
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if not data or data.get("code") != 0:
            logger.error(f"删除文件失败: {data}")
            return False

        task_id = data.get("data", {}).get("task_id")
        if not task_id:
            return True

        start = time.time()
        while time.time() - start < timeout:
            task_data = self._drive_request(
                "GET",
                f"{QUARK_SHARE_HOST}/1/clouddrive/task",
                params={"task_id": task_id, "retry_index": 0},
                timeout=20,
            )
            if task_data and task_data.get("code") == 0:
                status = task_data.get("data", {}).get("status")
                if status == 2:
                    logger.info(f"删除完成: {fid_list}")
                    return True
                if status and int(status) < 0:
                    logger.error(f"删除任务失败: {task_data}")
                    return False
            time.sleep(1)

        logger.warning(f"删除任务等待超时: {task_id}")
        return False

    def _wait_save_task(
        self,
        task_id: str,
        max_attempts: int = 40,
        interval: float = 2.0,
    ) -> List[str]:
        """轮询转存任务，返回保存后的顶层 fid 列表。

        服务端任务高峰期（凌晨批量转存）可能排队超过一分钟才完成，
        轮询窗口给到约两分半，避免任务实际会完成却提前放弃。
        """
        url = f"{QUARK_SHARE_HOST}/1/clouddrive/task"
        for attempt in range(max_attempts):
            time.sleep(interval)
            data = self._drive_request(
                "GET",
                url,
                params={"task_id": task_id, "retry_index": 0},
                timeout=20,
            )
            if not data or data.get("code") != 0:
                continue
            task_data = data.get("data", {})
            status = task_data.get("status")
            if status == 2:
                save_as = task_data.get("save_as", {})
                return save_as.get("save_as_top_fids", [])
            if status and int(status) < 0:
                logger.error(f"转存任务失败: {task_data}")
                return []
        logger.warning(f"转存任务轮询超时: {task_id}")
        return []

    def rename_file(self, fid: str, new_name: str) -> bool:
        """重命名网盘中的文件/文件夹。

        夸克不接受文件名里的半角“/”（API 返回 bad file name），
        发送前替换为全角“／”（如片名“19/20”）。
        """
        if not fid or not new_name:
            return False

        if "/" in new_name:
            new_name = new_name.replace("/", "／")

        url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/rename"
        payload = {"fid": fid, "file_name": new_name}
        data = self._drive_request(
            "POST",
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if data and data.get("code") == 0:
            logger.info(f"重命名成功: {fid} -> {new_name}")
            return True

        logger.error(f"重命名失败: {fid} -> {new_name}, 响应: {data}")
        return False

    @staticmethod
    def _oss_time() -> str:
        """生成 OSS 签名需要的 GMT 时间字符串。"""
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    def _oss_request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """对 OSS 直传请求（PUT/POST）做网络层重试。

        仅对连接断开、超时等网络异常重试，最多 3 次，指数退避。
        调用方仍需自行检查 HTTP 状态码。
        """
        max_retries = kwargs.pop("retries", 3)
        timeout = kwargs.pop("timeout", 300)
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.request(
                    method, url, timeout=timeout, **kwargs
                )
                return response
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"OSS {method} 请求异常: {e}，"
                        f"{attempt + 1} 秒后重试（{attempt}/{max_retries}）"
                    )
                    time.sleep(2 ** attempt)
                    continue
                logger.error(f"OSS {method} 请求异常: {e}")

        raise last_exception

    @staticmethod
    def _build_part_auth_meta(
        mime_type: str,
        utc_time: str,
        bucket: str,
        obj_key: str,
        part_number: int,
        upload_id: str,
    ) -> str:
        """构造分片上传的 OSS Authorization 签名原文。"""
        return (
            f"PUT\n\n{mime_type}\n{utc_time}\n"
            f"x-oss-date:{utc_time}\n"
            "x-oss-user-agent:aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit\n"
            f"/{bucket}/{obj_key}?partNumber={part_number}&uploadId={upload_id}"
        )

    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        pdir_fid: str,
    ) -> Optional[str]:
        """上传文件（字节数据）到夸克网盘指定目录。

        实现参考 quarkpan-rs 的上传流程：预上传 -> 更新哈希 -> 分片上传到 OSS
        -> POST 完成合并 -> finish。返回上传后的文件 fid，失败返回 None。
        """
        if not self.cookie or not file_data:
            logger.warning("Cookie 为空或文件数据为空，跳过上传")
            return None

        size = len(file_data)
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        md5_hash = hashlib.md5(file_data).hexdigest()
        sha1_hash = hashlib.sha1(file_data).hexdigest()
        now_ms = int(time.time() * 1000)

        # 1. 预上传
        pre_url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/upload/pre"
        payload = {
            "ccp_hash_update": True,
            "parallel_upload": False,
            "pdir_fid": pdir_fid,
            "dir_name": "",
            "size": size,
            "file_name": file_name,
            "format_type": mime_type,
            "l_updated_at": now_ms,
            "l_created_at": now_ms,
        }
        pre = self._drive_request("POST", pre_url, json=payload, timeout=60)
        if not pre or pre.get("code") != 0:
            logger.warning(f"预上传失败: {pre}")
            return None

        data = pre.get("data", {})
        if data.get("finish"):
            return data.get("fid")

        task_id = data.get("task_id")
        auth_info = data.get("auth_info", "")
        upload_id = data.get("upload_id", "")
        obj_key = data.get("obj_key", "")
        bucket = data.get("bucket", "ul-zb")
        callback = data.get("callback", {})
        upload_url_host = data.get("upload_url", "pds.quark.cn").split("://", 1)[-1]

        if not all([task_id, upload_id, obj_key, auth_info]):
            logger.warning(f"预上传返回字段不完整: {data}")
            return None

        # 2. 更新文件哈希（支持秒传）
        hash_url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/update/hash"
        hash_resp = self._drive_request(
            "POST",
            hash_url,
            json={"task_id": task_id, "md5": md5_hash, "sha1": sha1_hash},
            timeout=60,
        )
        if hash_resp and hash_resp.get("data", {}).get("finish"):
            return hash_resp.get("data", {}).get("fid") or data.get("fid")

        # 3. 分片上传
        part_size = pre.get("metadata", {}).get("part_size", 4 * 1024 * 1024)
        if part_size <= 0:
            part_size = 4 * 1024 * 1024
        total_parts = (size + part_size - 1) // part_size
        etags: List[str] = []

        for part_number in range(1, total_parts + 1):
            start = (part_number - 1) * part_size
            end = min(start + part_size, size)
            chunk = file_data[start:end]
            utc_time = self._oss_time()

            auth_meta = self._build_part_auth_meta(
                mime_type, utc_time, bucket, obj_key, part_number, upload_id
            )
            auth_resp = self._drive_request(
                "POST",
                f"{QUARK_SHARE_HOST}/1/clouddrive/file/upload/auth",
                json={
                    "task_id": task_id,
                    "auth_info": auth_info,
                    "auth_meta": auth_meta,
                },
                timeout=60,
            )
            if not auth_resp or auth_resp.get("code") != 0:
                logger.warning(f"获取分片 {part_number} 上传授权失败: {auth_resp}")
                return None

            auth_key = auth_resp.get("data", {}).get("auth_key", "")
            oss_url = (
                f"https://{bucket}.{upload_url_host}/{obj_key}"
                f"?partNumber={part_number}&uploadId={upload_id}"
            )
            headers = {
                "Content-Type": mime_type,
                "x-oss-date": utc_time,
                "x-oss-user-agent": "aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit",
                "Authorization": auth_key,
                "Referer": "https://pan.quark.cn/",
            }
            put_resp = self._oss_request_with_retry(
                "PUT", oss_url, data=chunk, headers=headers, timeout=300
            )
            if put_resp.status_code != 200:
                logger.warning(
                    f"上传分片 {part_number} 失败: {put_resp.status_code} {put_resp.text[:200]}"
                )
                return None

            etag = put_resp.headers.get("ETag", "").strip('"')
            if not etag:
                logger.warning(f"分片 {part_number} 上传成功但未返回 ETag")
                return None
            etags.append(etag)

        # 4. POST 完成合并
        xml_parts = [
            f"<Part>\n<PartNumber>{i}</PartNumber>\n<ETag>{etag}</ETag>\n</Part>"
            for i, etag in enumerate(etags, start=1)
        ]
        xml_body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<CompleteMultipartUpload>\n"
            + "\n".join(xml_parts)
            + "\n</CompleteMultipartUpload>"
        )
        xml_md5 = base64.b64encode(hashlib.md5(xml_body.encode("utf-8")).digest()).decode("utf-8")
        callback_b64 = base64.b64encode(
            json.dumps(callback, separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")
        commit_utc = self._oss_time()
        commit_auth_meta = (
            f"POST\n{xml_md5}\napplication/xml\n{commit_utc}\n"
            f"x-oss-callback:{callback_b64}\n"
            f"x-oss-date:{commit_utc}\n"
            "x-oss-user-agent:aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit\n"
            f"/{bucket}/{obj_key}?uploadId={upload_id}"
        )
        commit_auth_resp = self._drive_request(
            "POST",
            f"{QUARK_SHARE_HOST}/1/clouddrive/file/upload/auth",
            json={
                "task_id": task_id,
                "auth_info": auth_info,
                "auth_meta": commit_auth_meta,
            },
            timeout=60,
        )
        if not commit_auth_resp or commit_auth_resp.get("code") != 0:
            logger.warning(f"获取合并授权失败: {commit_auth_resp}")
            return None

        commit_auth_key = commit_auth_resp.get("data", {}).get("auth_key", "")
        commit_url = f"https://{bucket}.{upload_url_host}/{obj_key}?uploadId={upload_id}"
        commit_headers = {
            "Content-Type": "application/xml",
            "Content-MD5": xml_md5,
            "x-oss-callback": callback_b64,
            "x-oss-date": commit_utc,
            "x-oss-user-agent": "aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit",
            "Authorization": commit_auth_key,
            "Referer": "https://pan.quark.cn/",
        }
        post_resp = self._oss_request_with_retry(
            "POST", commit_url, data=xml_body, headers=commit_headers, timeout=300
        )
        if post_resp.status_code not in (200, 203):
            logger.warning(f"合并分片失败: {post_resp.status_code} {post_resp.text[:200]}")
            return None

        # 5. 通知夸克服务器上传完成
        finish_url = f"{QUARK_SHARE_HOST}/1/clouddrive/file/upload/finish"
        finish_resp = self._drive_request(
            "POST",
            finish_url,
            json={"task_id": task_id, "obj_key": obj_key},
            timeout=60,
        )
        if not finish_resp or finish_resp.get("code") != 0:
            logger.warning(f"完成上传失败: {finish_resp}")
            return None

        logger.info(f"上传成功: {file_name} -> fid={data.get('fid')}")
        return data.get("fid")

    def save_and_rename(
        self,
        share_url: str,
        items: List[Dict],
        target_dir_path: str,
        name_generator: Callable[[Dict], Optional[str]],
    ) -> List[Dict]:
        """将分享项转存到目标目录并按 name_generator 结果重命名。

        返回每个 item 附加了 saved_fid / renamed / error 的列表。
        """
        results = []
        if not items:
            return results

        target_fid = self.find_or_create_dir(target_dir_path)
        if not target_fid:
            logger.error(f"无法找到或创建目标目录: {target_dir_path}")
            for item in items:
                results.append({**item, "error": "target_dir_not_found"})
            return results

        # 按 item 分批转存
        saved_items = self.save_share_files(share_url, items, target_fid)

        # 建立原始 fid -> 保存后 fid 的映射
        saved_fid_map: Dict[str, str] = {}
        for saved in saved_items:
            original_fid = saved.get("original_fid")
            saved_fid = saved.get("fid")
            if original_fid and saved_fid:
                saved_fid_map[original_fid] = saved_fid

        for item in items:
            original_fid = item.get("fid")
            new_name = name_generator(item)
            saved_fid = saved_fid_map.get(original_fid)

            result = dict(item)
            result["target_dir_fid"] = target_fid
            result["saved_fid"] = saved_fid

            if not saved_fid:
                result["error"] = "save_failed"
                results.append(result)
                continue

            if new_name:
                renamed = self.rename_file(saved_fid, new_name)
                result["renamed"] = renamed
                result["new_name"] = new_name if renamed else None
            else:
                result["renamed"] = False
                result["new_name"] = None

            results.append(result)

        return results
