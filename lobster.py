#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙虾 - 拓木映画微博爬虫（PC端新版Cookie适配）
"""

import requests
import re
import json
import time
import random
import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lobster.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class MovieInfo:
    chinese_name: Optional[str] = None
    foreign_name: Optional[str] = None
    year: Optional[int] = None
    director: Optional[str] = None
    writer: Optional[str] = None
    cast: List[str] = field(default_factory=list)
    language: Optional[str] = None
    subtitle: Optional[str] = None
    genre: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[str] = None
    awards: Optional[str] = None
    season: Optional[int] = None
    season_raw: Optional[str] = None
    season_extra: Optional[str] = None
    episodes: Optional[int] = None
    source_link: Optional[str] = None
    weibo_id: Optional[str] = None
    publish_time: Optional[str] = None
    raw_text: Optional[str] = None
    director_pos: Optional[int] = None
    writer_pos: Optional[int] = None
    cast_pos: Optional[int] = None

    def __post_init__(self):
        if self.cast is None:
            self.cast = []

    def generate_filename(self) -> str:
        """按格式生成文件名：中文名 外文名 年份（主演 导演 编剧 获奖 评级类别类型 季数集数 语言字幕）"""

        def _safe(text):
            if not text:
                return ""
            import re as _re
            text = _re.sub(r'[<>"/\|?*]', '', str(text))
            text = text.replace(':', '：')
            return text.strip()

        parts = []

        if self.chinese_name:
            parts.append(_safe(self.chinese_name))

        if self.foreign_name:
            parts.append(_safe(self.foreign_name))

        if self.year:
            parts.append(str(self.year))

        bracket_parts = []

        # 改编自类信息放在导演/主演之前
        if self.awards and self.awards.startswith('改编自'):
            bracket_parts.append(_safe(self.awards))

        ordered_parts = []

        if self.cast:
            invalid_cast_keywords = ['悬疑', '犯罪', '高分', '冷门', '热门', '导演', '主演', '喜剧', '惊悚', '恐怖', '动画', '纪录片', '剧情', '奇幻', '治愈', '音乐', '历史', '美食', '科幻', '动作', '爱情', '战争', '传记', '运动', '儿童', '短片', '剧集', '电影']
            cast_clean = [c for c in self.cast if len(c) < 15 and c not in invalid_cast_keywords and not c.isdigit()]
            if cast_clean:
                cast_str = '、'.join(cast_clean[:3])
                ordered_parts.append((self.cast_pos if self.cast_pos is not None else 9999, f"{_safe(cast_str)}主演"))

        if self.director:
            director_clean = self.director.strip()
            invalid_keywords = ['中字', '语', '字', '导演', '主演', '高分', '热门', '冷门', '悬疑', '犯罪', '喜剧', '惊悚', '恐怖', '动画', '纪录片', '剧情', '奇幻', '治愈', '音乐', '历史', '美食', '科幻', '动作', '爱情', '战争', '传记', '运动', '儿童', '短片', '剧集', '电影', '作品', '日语', '中日', '双字', '字幕', '见平', '推荐', '全', '集', '季']
            is_valid = (
                director_clean
                and len(director_clean) < 15
                and not any(kw in director_clean for kw in invalid_keywords)
                and not director_clean.isdigit()
                and not re.search(r'全\d+集|第\d+季', director_clean)
            )
            if is_valid:
                ordered_parts.append((self.director_pos if self.director_pos is not None else 9999, f"{_safe(director_clean)}导演"))

        if self.writer:
            writer_clean = self.writer.strip()
            invalid_writer_keywords = ['中字', '语', '字', '导演', '主演', '高分', '热门', '冷门', '悬疑', '犯罪', '喜剧', '惊悚', '恐怖', '动画', '纪录片', '剧情', '奇幻', '治愈', '音乐', '历史', '美食', '科幻', '动作', '爱情', '战争', '传记', '运动', '儿童', '短片', '剧集', '电影', '作品', '日语', '中日', '双字', '字幕', '见平', '推荐', '全', '集', '季']
            is_valid = (
                writer_clean
                and len(writer_clean) < 15
                and not any(kw in writer_clean for kw in invalid_writer_keywords)
                and not writer_clean.isdigit()
            )
            if is_valid:
                ordered_parts.append((self.writer_pos if self.writer_pos is not None else 9999, f"{_safe(writer_clean)}编剧"))
        
        ordered_parts.sort(key=lambda x: x[0])
        bracket_parts.extend([p[1] for p in ordered_parts])

        if self.awards and not self.awards.startswith('改编自'):
            bracket_parts.append(_safe(self.awards))

        combined = []
        if self.rating:
            combined.append(_safe(self.rating))
        # 当 genre 为 "短片" 时，category 不显示（避免与奖项中的"短片"重复）
        if self.category and not (self.genre == "短片" and self.category == "短片"):
            cat_parts = [c for c in self.category.split('/') if c]
            # 过滤掉与 genre 有包含/被包含关系的部分，避免"纪录"+"纪录片"="纪录纪录片"
            filtered = [c for c in cat_parts if not (self.genre and (c in self.genre or self.genre in c))]
            if filtered:
                combined.append(''.join(filtered))
        # genre 显示条件
        show_genre = self.genre and (self.rating or self.category or (self.genre in ("剧集", "动画剧集") and (self.season or self.episodes or self.season_extra)))
        # category 已包含 genre 时不重复
        if show_genre and self.category and self.genre in self.category.replace('/', ''):
            show_genre = False
        # 短片不显示 genre
        if show_genre and self.genre == "短片":
            show_genre = False
        if show_genre and self.genre:
            combined.append(self.genre)
        if combined:
            bracket_parts.append(''.join(combined))

        season_ep = []
        if self.season_extra:
            season_ep.append(self.season_extra)
        elif self.season_raw:
            season_ep.append(f"{self.season_raw}季")
        elif self.season:
            season_ep.append(f"第{self.season}季")
        if self.episodes:
            season_ep.append(f"全{self.episodes}集")
        if season_ep:
            bracket_parts.append(' '.join(season_ep))

        if self.language or self.subtitle:
            lang_str = ''
            if self.language:
                lang_str += self.language
            if self.subtitle:
                lang_str += self.subtitle
            bracket_parts.append(_safe(lang_str))

        if bracket_parts:
            parts.append(f"（{' '.join(bracket_parts)}）")

        return " ".join(parts) if parts else "未命名"



class WeiboCrawler:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.uid = "7608233324"
        self.processed_ids = self._load_processed_ids()

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            self.cookie = config.get("weibo_cookie", "")
            logger.info(f"Cookie 加载成功，长度: {len(self.cookie)}")
        except Exception as e:
            logger.error(f"加载 Cookie 失败: {e}")
            self.cookie = ""

        self._init_session()

    def _init_session(self):
        headers = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://weibo.com/u/7608233324",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
        }

        xsrf_match = re.search(r'XSRF-TOKEN=([^;]+)', self.cookie)
        if xsrf_match:
            headers["X-XSRF-TOKEN"] = xsrf_match.group(1)
            logger.info(f"XSRF-TOKEN: {xsrf_match.group(1)[:20]}...")

        if self.cookie:
            headers["Cookie"] = self.cookie

        self.session.headers.update(headers)

        logger.info("初始化会话，访问微博主页...")
        self._safe_request("GET", f"https://weibo.com/u/{self.uid}")

    def _safe_request(self, method, url, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                delay = random.uniform(5, 10)
                logger.info(f"等待 {delay:.1f} 秒后请求...")
                time.sleep(delay)

                self.session.headers["User-Agent"] = random.choice(self.USER_AGENTS)

                response = self.session.request(method, url, timeout=30, **kwargs)

                if response.status_code == 200:
                    return response
                elif response.status_code == 418:
                    logger.warning("触发反爬机制，延长等待...")
                    time.sleep(random.uniform(60, 120))
                else:
                    logger.warning(f"请求失败: {response.status_code}")

            except Exception as e:
                logger.error(f"请求异常: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(30, 60))

        return None

    def _load_processed_ids(self) -> set:
        filename = "processed_weibo.json"
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return set(json.load(f))
        return set()

    def _save_processed_id(self, weibo_id: str):
        self.processed_ids.add(weibo_id)
        filename = "processed_weibo.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(list(self.processed_ids), f, ensure_ascii=False)

    def get_weibo_list(self, page: int = 1) -> List[Dict]:
        apis = [
            ("https://weibo.com/ajax/statuses/mymblog", {"uid": self.uid, "page": page, "feature": 0}),
            ("https://weibo.com/ajax/statuses/container_timeline", {"containerid": f"107603{self.uid}", "page": page}),
        ]

        for url, params in apis:
            logger.info(f"尝试接口: {url}")
            response = self._safe_request("GET", url, params=params)

            if not response:
                continue

            try:
                raw_text = response.text[:2000]
                logger.info(f"原始响应: {raw_text[:500]}...")
            except:
                pass

            try:
                data = response.json()
                logger.info(f"响应: ok={data.get('ok')}")

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
                        logger.info(f"  微博 {i}: ID={w.get('id')}, 内容={text[:50]}...")

                    return weibo_list
                else:
                    logger.warning(f"接口返回失败: {data.get('msg')}")
            except Exception as e:
                logger.error(f"解析失败: {e}")

        return []

    def get_comments(self, weibo_id: str) -> List[Dict]:
        """获取评论（PC 端 API）"""
        url = "https://weibo.com/ajax/statuses/buildComments"
        params = {
            "flow": 0,
            "is_reload": 1,
            "id": weibo_id,
            "is_show_bulletin": 2,
            "is_mix": 0,
            "count": 20,
        }

        response = self._safe_request("GET", url, params=params)
        if not response:
            return []

        try:
            data = response.json()
            if data.get("ok") == 1:
                comments = data.get("data", [])
                for comment in comments:
                    url_struct = comment.get("url_struct", [])
                    for url_item in url_struct:
                        short_url = url_item.get("short_url", "")
                        long_url = url_item.get("long_url", "")
                        if long_url and "quark" in long_url:
                            comment["_quark_link"] = long_url
                            logger.info(f"  从url_struct找到夸克链接: {long_url}")
                        elif short_url:
                            comment["_short_link"] = short_url

                    topic_struct = comment.get("topic_struct", [])
                    for topic in topic_struct:
                        topic_url = topic.get("topic_url", "")
                        if topic_url and "quark" in topic_url:
                            comment["_quark_link"] = topic_url

                    page_info = comment.get("page_info", {})
                    if page_info:
                        media_url = page_info.get("media_info", {}).get("stream_url", "")
                        if media_url and "quark" in media_url:
                            comment["_quark_link"] = media_url
                        page_url = page_info.get("page_url", "")
                        if page_url and "quark" in page_url:
                            comment["_quark_link"] = page_url

                return comments
            else:
                logger.warning(f"获取评论失败: {data.get('msg')}")
        except Exception as e:
            logger.error(f"解析评论失败: {e}")

        return []

    def extract_quark_links(self, text: str) -> List[str]:
        """从文本中提取夸克网盘链接"""
        if not text:
            return []

        links = []

        quark_pattern = r'https?://pan\.quark\.cn/s/[a-zA-Z0-9]+'
        links.extend(re.findall(quark_pattern, text))

        sinaurl_pattern = r'https?://weibo\.cn/sinaurl\?u=([^&\s]+)'
        sina_links = re.findall(sinaurl_pattern, text)
        for encoded_url in sina_links:
            decoded = urllib.parse.unquote(encoded_url)
            if "quark" in decoded:
                links.append(decoded)

        tcn_pattern = r'https?://t\.cn/[a-zA-Z0-9]+'
        tcn_links = re.findall(tcn_pattern, text)
        for tcn in tcn_links:
            expanded = self._expand_short_link(tcn)
            if expanded and "quark" in expanded:
                links.append(expanded)

        plain_pattern = r'pan\.quark\.cn/s/([a-zA-Z0-9]+)'
        plain_links = re.findall(plain_pattern, text)
        for pl in plain_links:
            links.append(f"https://pan.quark.cn/s/{pl}")

        return list(dict.fromkeys(links))

    def _expand_short_link(self, short_url: str) -> Optional[str]:
        """展开微博短链获取真实URL"""
        if not short_url:
            return None

        try:
            response = self.session.head(short_url, allow_redirects=True, timeout=10)
            if response.status_code == 200:
                real_url = response.url
                logger.info(f"短链展开: {short_url} -> {real_url}")
                return real_url
        except Exception as e:
            logger.error(f"展开短链失败: {e}")

        return None


class MovieExtractor:
    """影视信息提取器"""

    def __init__(self):
        self.patterns = {
            "chinese_name": r'《([^》]+)》',
            "language_subtitle": r'(法英语|俄英语|日英语|德英语|韩日英语|日韩语|乌兹别克俄语|国日双语|粤国语|法波兰俄语|国闽南语|国语|英语|法语|日语|韩语|德语|西班牙语|瑞典语|匈牙利语|闽南语|捷克语|波斯语|印地语|孟加拉语|泰语|斯洛伐克语|芬兰语|无对[白话]|粤语|俄语|白俄罗斯语|意大利语|葡萄牙语|荷兰语|波兰语|土耳其语|阿拉伯语|希伯来语|冰岛语|挪威语|丹麦语|乌兹别克语|米沙鄢语)(?:语)?([中英\w]*字|双语|中字|中英字幕|中英双字|内嵌字幕|外挂字幕|硬字幕|软字幕|中日双字)',
            "episodes": r'全(\d+)集',
            "season": r'(?:第|S|Season\s*|全)([0-9一二两三四五六七八九十]+)(?:季|季季)',
            "year": r'(?<![全共第])(19|20)\d{2}(?![集季])',
        }

        self.categories = ["悬疑", "惊悚", "喜剧", "恐怖", "犯罪", "爱情", "战争", "科幻", "奇幻", "治愈", "音乐", "历史", "美食", "传记", "运动", "儿童", "短片", "动作", "剧情", "西部", "自然", "纪录"]

        self.ratings = ["高分", "热门", "冷门", "五星满分", "奥斯卡最佳", "戛纳电影节金棕榈奖", "柏林电影节金熊奖", "威尼斯电影节金狮奖", "圣丹斯电影节", "法国凯撒电影奖", "戛纳电影节金摄影机奖", "圣塞巴斯蒂安电影节金贝壳奖", "塔林黑夜电影节", "冷门高分", "热门高分"]

        self.non_movie_keywords = [
            "今天是", "周年", "去世", "生日", "写真", "构图",
            "票房破", "破亿", "定档", "出了会发", "海报释出", "海报",
            "最新剧集", "第二季", "第三季", "第四季", "第五季",
            "杀青", "开机", "入围名单", "提名名单", "获奖名单",
        ]

    def is_non_movie_content(self, text: str) -> bool:
        if not text:
            return True

        non_resource_keywords = ["写真", "构图", "美术", "出了会发", "海报释出", "海报", "将于", "入围名单", "提名名单", "获奖名单", "获奖公布", "获奖信息"]
        for kw in non_resource_keywords:
            if kw in text:
                return True

        if "《" in text and "》" in text:
            for keyword in ["今天是", "周年", "去世", "生日", "票房已破"]:
                if keyword in text:
                    return True
            has_resource_hint = any(kw in text for kw in ["导演", "主演", "中字", "夸克", "pan.quark"])
            has_film_festival = any(kw in text for kw in ["戛纳", "柏林", "威尼斯", "奥斯卡", "圣丹斯", "凯撒", "金棕榈", "金熊", "金狮", "金摄影机", "金贝壳", "电影节", "评审团", "主竞赛", "洛加诺", "洛迦诺", "金豹奖"])
            if has_resource_hint or has_film_festival:
                return False
            return False

        if "《" not in text:
            has_movie_keywords = any(kw in text for kw in ["导演", "主演", "电影", "剧集", "动画", "纪录片", "中字"])
            if not has_movie_keywords:
                return True

        for keyword in self.non_movie_keywords:
            if keyword in text:
                return True

        return False

    def extract(self, text: str, weibo_id: str = None, publish_time: str = None) -> Optional[MovieInfo]:
        """从微博文本提取影视信息"""

        if self.is_non_movie_content(text):
            logger.info(f"非影视内容，跳过: {text[:30]}...")
            return None

        info = MovieInfo(raw_text=text, weibo_id=weibo_id, publish_time=publish_time)

        if not text:
            return info

        names = re.findall(self.patterns["chinese_name"], text)
        if names:
            info.chinese_name = names[0]

        if info.chinese_name:
            fn_match = re.search(r'《' + re.escape(info.chinese_name) + r'》\s*([（(])([^）)]+)([）)])', text)
            if fn_match:
                info.foreign_name = fn_match.group(2).strip()
            else:
                fn_match2 = re.search(r'《' + re.escape(info.chinese_name) + r'》\s*/\s*([^《》\s][^《》]{1,50})', text)
                if fn_match2:
                    info.foreign_name = fn_match2.group(1).strip()
                else:
                    all_names = re.findall(r'《([^》]+)》', text)
                    if len(all_names) >= 2 and info.chinese_name in all_names:
                        idx = all_names.index(info.chinese_name)
                        if idx + 1 < len(all_names):
                            candidate = all_names[idx + 1]
                            if re.search(r'[a-zA-Z]', candidate):
                                info.foreign_name = candidate

        # 提取导演
        invalid_director_keywords = ['语', '字', '中', '英', '导演', '主演', '编剧', '获奖', '提名', '作品', '推荐', '热门', '冷门', '高分', '悬疑', '惊悚', '喜剧', '恐怖', '犯罪', '动画', '纪录片', '剧情', '奇幻', '治愈', '音乐', '历史', '美食', '科幻', '动作', '爱情', '战争', '传记', '运动', '儿童', '短片', '剧集', '电影', '全', '集', '季']
        director_candidates = []
        director_positions = []
        for m in re.finditer(r'([^《》\n\s]{2,15}?)导演(?:作品|电影|剧集|纪录片|动画|推荐|全\d+集|第\d+季|\s|$)', text):
            director_candidates.append(m.group(1).strip())
            director_positions.append(m.start())
        for m in re.finditer(r'([^《》\n\s]{2,15}?)执导', text):
            director_candidates.append(m.group(1).strip())
            director_positions.append(m.start())
        for m in re.finditer(r'导演[:：]?\s*([^《》\n,，/、\s]{2,15})', text):
            director_candidates.append(m.group(1).strip())
            director_positions.append(m.start())
        
        best_director = None
        best_director_pos = None
        for i, cand in enumerate(director_candidates):
            if len(cand) < 15 and not any(kw in cand for kw in invalid_director_keywords) and not cand.isdigit():
                if best_director is None or len(cand) > len(best_director):
                    best_director = cand
                    best_director_pos = director_positions[i]
        if best_director:
            info.director = best_director
            info.director_pos = best_director_pos

        # 提取编剧
        invalid_writer_keywords = ['语', '字', '中', '英', '导演', '主演', '编剧', '获奖', '提名', '作品', '推荐', '热门', '冷门', '高分', '悬疑', '惊悚', '喜剧', '恐怖', '犯罪', '动画', '纪录片', '剧情', '奇幻', '治愈', '音乐', '历史', '美食', '科幻', '动作', '爱情', '战争', '传记', '运动', '儿童', '短片', '剧集', '电影', '全', '集', '季']
        writer_candidates = []
        writer_positions = []
        for m in re.finditer(r'([^《》\n\s]{2,15}?)编剧', text):
            writer_candidates.append(m.group(1).strip())
            writer_positions.append(m.start())
        for m in re.finditer(r'编剧[:：]?\s*([^《》\n,，/、\s]{2,15})', text):
            writer_candidates.append(m.group(1).strip())
            writer_positions.append(m.start())
        
        best_writer = None
        best_writer_pos = None
        for i, cand in enumerate(writer_candidates):
            if len(cand) < 15 and not any(kw in cand for kw in invalid_writer_keywords) and not cand.isdigit():
                if best_writer is None or len(cand) > len(best_writer):
                    best_writer = cand
                    best_writer_pos = writer_positions[i]
        if best_writer:
            info.writer = best_writer
            info.writer_pos = best_writer_pos

        # 提取主演
        invalid_cast_keywords = ['悬疑', '犯罪', '高分', '冷门', '热门', '导演', '主演', '喜剧', '惊悚', '恐怖', '动画', '纪录片', '剧情', '奇幻', '治愈', '音乐', '历史', '美食', '科幻', '动作', '爱情', '战争', '传记', '运动', '儿童', '短片', '剧集', '电影']
        cast_candidates = []
        
        cast_match1 = re.search(r'([^《》\n\s]{2,15}(?:[/、，,][^《》\n\s]{2,15})*)\s*(?:主演|出演)', text)
        if cast_match1:
            cast_candidates.append(cast_match1.group(1).strip())
        
        cast_match2 = re.search(r'(?:主演|出演)[:：]\s*([^《》\n]{2,40}?)(?:\s|，|,|/|、|$)', text)
        if cast_match2:
            cast_candidates.append(cast_match2.group(1).strip())
        
        cast_match3 = re.search(r'》\s*([^《》\n]{2,30}?)\s*(?:主演|出演)', text)
        if cast_match3:
            cast_candidates.append(cast_match3.group(1).strip())

        best_cast = []
        best_cast_pos = None
        for raw in cast_candidates:
            raw = re.sub(r'\s*(主演|出演)$', '', raw).strip()
            raw = re.sub(r'^(高分|热门|冷门|悬疑|犯罪|喜剧|惊悚|恐怖|动画|纪录片|剧情|奇幻|治愈|音乐|历史|美食|科幻|动作|爱情|战争|传记|运动|儿童|短片)', '', raw).strip()
            cast_list = [c.strip() for c in re.split(r'[/、，,\s]+', raw) if c.strip() and len(c.strip()) > 1 and len(c.strip()) < 15]
            cast_list = [c for c in cast_list if not any(kw in c for kw in invalid_cast_keywords) and not c.isdigit() and '导演' not in c and '执导' not in c and not re.search(r'全\d+集|第\d+季', c)]
            if len(cast_list) > len(best_cast):
                best_cast = cast_list
                pos = text.find(raw + '主演') if raw + '主演' in text else text.find(raw + '出演')
                if pos == -1:
                    pos = text.find('主演') if '主演' in text else text.find('出演')
                best_cast_pos = pos if pos != -1 else None

        if best_cast:
            info.cast = best_cast
            info.cast_pos = best_cast_pos

        # 提取类别 - 只从最后一个书名号后的文本中提取，避免标题关键词混入
        text_after_title = text
        last_guillemet_end = text.rfind('》')
        if last_guillemet_end != -1:
            text_after_title = text[last_guillemet_end + 1:]

        found_categories = []
        for cat in self.categories:
            if cat in text_after_title:
                # 避免 genre="纪录片" 时 category 重复提取"纪录"
                if info.genre == "纪录片" and cat == "纪录":
                    continue
                found_categories.append(cat)
        if found_categories:
            info.category = '/'.join(found_categories)

        # 提取获奖情况
        awards_patterns = [
            r'(圣丹斯电影节(?:评审团大奖|短片评审团大奖)?(?:提名|获奖)作品?)',
            r'(戛纳电影节金棕榈奖(?:提名|获奖)?作品?)',
            r'(柏林电影节金熊奖(?:提名|获奖)?作品?)',
            r'(柏林电影节展映作品)',
            r'(威尼斯电影节金狮奖(?:提名|获奖)?作品?)',
            r'(法国凯撒电影奖最佳影片(?:提名|获奖)?作品?)',
            r'(戛纳电影节金摄影机奖(?:提名|获奖)?作品?)',
            r'(圣塞巴斯蒂安电影节金贝壳奖(?:提名|获奖)?作品?)',
            r'(塔林黑夜电影节(?:主竞赛单元)?(?:提名|获奖)?作品?)',
            r'(奥斯卡最佳(?:动画长片|影片)?(?:获奖)?作品?)',
            r'(法国电影手册五星满分)',
            r'(日本电影学院奖最佳影片(?:提名|获奖)?作品?)',
            r'(报知映画赏最佳影片(?:提名|获奖)?作品?)',
            r'(洛加诺电影节当代电影人单元金豹奖提名)',
            r'(洛迦诺电影节当代电影人单元金豹奖提名)',
            r'(金马最佳影片提名作品)',
            r'(安妮奖最佳独立动画长片提名作品?)',
        ]
        found_awards = []
        for pattern in awards_patterns:
            match = re.search(pattern, text)
            if match:
                award_text = match.group(1)
                if not any(award_text in existing and award_text != existing for existing in found_awards):
                    found_awards = [existing for existing in found_awards if existing not in award_text]
                    found_awards.append(award_text)
        if found_awards:
            info.awards = ' '.join(found_awards)

        # 提取改编信息
        adaptation_match = re.search(r'(改编自[^《》]{0,20}《[^》]+》)', text)
        if adaptation_match:
            if info.awards:
                info.awards = adaptation_match.group(1) + ' ' + info.awards
            else:
                info.awards = adaptation_match.group(1)

        # 提取评级
        rating_patterns = [
            r'(冷门高分)',
            r'(热门高分)',
            r'(五星满分)',
            r'(高分)(?!原著)',
            r'(热门)',
            r'(冷门)',
        ]
        found_ratings = []
        for pattern in rating_patterns:
            match = re.search(pattern, text)
            if match:
                rating_text = match.group(1)
                if info.awards and rating_text in info.awards:
                    continue
                if any(rating_text in existing and rating_text != existing for existing in found_ratings):
                    continue
                found_ratings = [existing for existing in found_ratings if existing not in rating_text]
                found_ratings.append(rating_text)
        if found_ratings:
            info.rating = ' '.join(found_ratings)

        # 提取语言和字幕
        sub_patterns = ['中英双字', '中英字幕', '双语字幕', '内嵌字幕', '外挂字幕', '硬字幕', '软字幕', '中日双字', '中字', '双语']
        lang_names = ['法英语', '俄英语', '日英语', '德英语', '韩日英语', '日韩语', '乌兹别克俄语', '国日双语', '粤国语', '法波兰俄语', '国闽南语', '国语', '英语', '法语', '日语', '韩语', '德语', '西班牙语', '瑞典语', '匈牙利语', '闽南语', '捷克语', '波斯语', '印地语', '孟加拉语', '泰语', '斯洛伐克语', '芬兰语', '无对白', '粤语', '俄语', '白俄罗斯语', '意大利语', '葡萄牙语', '荷兰语', '波兰语', '土耳其语', '阿拉伯语', '希伯来语', '冰岛语', '挪威语', '丹麦语', '乌兹别克语', '米沙鄢语']
        lang_matched = False
        for sub_pat in sub_patterns:
            sub_idx = text.find(sub_pat)
            if sub_idx != -1:
                before = text[:sub_idx].rstrip()

                # 预处理斜杠分隔的组合语言
                slash_replacements = {
                    '法/英语': '法英语',
                    '俄/英语': '俄英语',
                    '日/英语': '日英语',
                    '德/英语': '德英语',
                    '英/德语': '英德语',
                    '韩/日/英语': '韩日英语',
                    '韩日/英语': '韩日英语',
                    '英/印地/孟加拉/法语': '英印地孟加拉法语',
                    '英/印地/孟加拉语': '英印地孟加拉语',
                    '英/法语': '英法语',
                    '法/德语': '法德语',
                    '国/闽南语': '国闽南语',
                    '粤/国语': '粤国语',
                    '乌兹别克/俄语': '乌兹别克俄语',
                    '法/波兰/俄语': '法波兰俄语',
                    '英/白俄罗斯/波兰语': '英白俄罗斯波兰语',
                    '日/韩语': '日韩语',
                    '韩/日语': '日韩语',
                }
                for old, new in sorted(slash_replacements.items(), key=lambda x: len(x[0]), reverse=True):
                    before = before.replace(old, new)

                found_langs = []
                temp = before

                # 优先匹配组合语言，避免被短语言截断
                priority_combo = ['韩日英语', '英白俄罗斯波兰语', '英印地孟加拉法语', '英印地孟加拉语', '法波兰俄语', '乌兹别克俄语']
                while temp:
                    matched = False
                    for combo in priority_combo:
                        if temp.endswith(combo):
                            found_langs.append(combo)
                            temp = temp[:-len(combo)].rstrip()
                            if temp.endswith('/') or temp.endswith('、'):
                                temp = temp[:-1].rstrip()
                            matched = True
                            break
                    if matched:
                        continue
                    for lang in sorted(lang_names, key=len, reverse=True):
                        if temp.endswith(lang):
                            found_langs.append(lang)
                            temp = temp[:-len(lang)].rstrip()
                            if temp.endswith('/') or temp.endswith('、'):
                                temp = temp[:-1].rstrip()
                            matched = True
                            break
                    if not matched:
                        break
                if found_langs:
                    info.language = ''.join(reversed(found_langs))
                    info.subtitle = sub_pat
                    lang_matched = True
                break

        if not lang_matched:
            lang_match = re.search(self.patterns["language_subtitle"], text)
            if lang_match:
                info.language = lang_match.group(1)
                info.subtitle = lang_match.group(2)
            else:
                fallback = re.search(r'(中英双语|中字|双语字幕|中英字幕|内嵌中字|外挂中字|中日双字)', text)
                if fallback:
                    info.subtitle = fallback.group(1)

        # 提取集数
        ep_match = re.search(self.patterns["episodes"], text)
        if ep_match:
            info.episodes = int(ep_match.group(1))

        # 提取季数
        season_match = re.search(self.patterns["season"], text)
        if season_match:
            raw = season_match.group(0)
            info.season_raw = re.sub(r'季+$', '', raw)
            season_str = season_match.group(1)
            chinese_nums = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
            if season_str in chinese_nums:
                info.season = chinese_nums[season_str]
                # 只在"全"开头时替换为阿拉伯数字，"第"开头保留中文
                if info.season_raw.startswith('全'):
                    info.season_raw = info.season_raw.replace(season_str, str(info.season))
            else:
                try:
                    info.season = int(season_str)
                except ValueError:
                    pass

        # 提取额外季数信息
        extra_season = re.search(r'(全\d+季\+番外\+花絮)', text)
        if extra_season:
            info.season_extra = extra_season.group(1)

        # 提取年份
        year_match = re.search(self.patterns["year"], text)
        if year_match:
            info.year = int(year_match.group(0))

        # 判断类型
        if "动画" in text and "剧集" in text:
            info.genre = "动画剧集"
        elif "纪录片" in text:
            info.genre = "纪录片"
        elif "短片" in text:
            info.genre = "短片"
        elif "剧集" in text:
            info.genre = "剧集"
        elif "动画" in text:
            info.genre = "动画"
        else:
            info.genre = "电影"

        return info


class Lobster:
    def __init__(self):
        self.crawler = WeiboCrawler()
        self.extractor = MovieExtractor()
        self.today = datetime.now().strftime("%Y-%m-%d")
        # 询问用户目标日期（默认为昨天）
        default_yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        user_input = input(f"请输入要抓取的目标日期（直接回车使用默认昨天 {default_yesterday}）: ").strip()
        self.yesterday = user_input if user_input else default_yesterday
        self.results = []

    def is_yesterday(self, publish_time) -> bool:
        """判断是否是目标日期发布的"""
        try:
            if isinstance(publish_time, (int, float)):
                dt = datetime.fromtimestamp(publish_time)
                return dt.strftime("%Y-%m-%d") == self.yesterday

            for fmt in ["%a %b %d %H:%M:%S %z %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(str(publish_time), fmt)
                    return dt.strftime("%Y-%m-%d") == self.yesterday
                except:
                    continue
        except:
            pass

        if "昨天" in str(publish_time):
            return True
        return False

    def process_weibo(self, weibo: Dict) -> Optional[MovieInfo]:
        """处理单条微博"""
        weibo_id = str(weibo.get("id", weibo.get("mid", "")))

        if not weibo_id or weibo_id in self.crawler.processed_ids:
            logger.info(f"跳过已处理微博: {weibo_id}")
            return None

        text = weibo.get("text", "")
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)

        publish_time = weibo.get("created_at", weibo.get("timestamp", ""))

        logger.info(f"处理微博 [{weibo_id}]: {text[:50]}...")

        if not self.is_yesterday(publish_time):
            logger.info(f"非目标日期发布: {publish_time}")
            return None

        info = self.extractor.extract(text, weibo_id, str(publish_time))

        if info is None:
            logger.info(f"跳过非影视内容")
            return None

        text_links = self.crawler.extract_quark_links(text)
        if text_links:
            info.source_link = text_links[0]
            logger.info(f"从正文找到夸克链接: {info.source_link}")

        if not info.source_link:
            logger.info(f"获取评论...")
            comments = self.crawler.get_comments(weibo_id)

            for i, comment in enumerate(comments[:3]):
                comment_text = comment.get("text", "")
                comment_text = re.sub(r'<[^>]+>', '', comment_text)
                quark_from_struct = comment.get("_quark_link", "")
                short_link = comment.get("_short_link", "")
                logger.info(f"  评论 {i}: {comment_text[:50]}... 结构化链接: {quark_from_struct[:40] if quark_from_struct else '无'} 短链: {short_link[:30] if short_link else '无'}")

            quark_links = []
            for comment in comments:
                if "_quark_link" in comment:
                    quark_links.append(comment["_quark_link"])
                    logger.info(f"  使用结构化夸克链接: {comment['_quark_link']}")

                if "_short_link" in comment:
                    expanded = self.crawler._expand_short_link(comment["_short_link"])
                    if expanded and "quark" in expanded:
                        quark_links.append(expanded)
                        logger.info(f"  短链展开为夸克链接: {expanded}")

                comment_text = comment.get("text", "")
                comment_text = re.sub(r'<[^>]+>', '', comment_text)
                links = self.crawler.extract_quark_links(comment_text)
                quark_links.extend(links)

            quark_links = list(dict.fromkeys(quark_links))

            if quark_links:
                info.source_link = quark_links[0]
                logger.info(f"从评论找到夸克链接: {info.source_link}")
            else:
                logger.info(f"  未找到夸克链接")

        self.crawler._save_processed_id(weibo_id)

        return info

    def run(self, max_pages: int = 6):
        """运行爬虫"""
        logger.info(f"=== 龙虾启动 [目标日期: {self.yesterday}] ===")

        for page in range(1, max_pages + 1):
            logger.info(f"获取第 {page} 页微博...")
            weibo_list = self.crawler.get_weibo_list(page)

            if not weibo_list:
                logger.info("没有更多微博")
                break

            for weibo in weibo_list:
                info = self.process_weibo(weibo)
                if info:
                    self.results.append(info)
                    logger.info(f"✅ 提取成功: {info.chinese_name or '未命名'}")
                    logger.info(f"   文件名: {info.generate_filename()}")
                    if info.source_link:
                        logger.info(f"   链接: {info.source_link}")

            has_yesterday = any(self.is_yesterday(w.get("created_at", w.get("timestamp", ""))) for w in weibo_list)
            if not has_yesterday and page > 2:
                logger.info("该页已无目标日期微博，停止")
                break

        self._save_results()
        logger.info(f"=== 完成，共处理 {len(self.results)} 条 ===")

        return self.results

    def _save_results(self):
        """保存结果到文件"""
        filename = f"results_{self.today}.json"
        data = [asdict(r) for r in self.results]
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存: {filename}")

        # 保存文件名列表
        txt_filename = f"filenames_{self.today}.txt"
        with open(txt_filename, "w", encoding="utf-8") as f:
            for i, info in enumerate(self.results, 1):
                f.write(f"{i}. {info.generate_filename()}\n")
        logger.info(f"文件名列表已保存: {txt_filename}")


if __name__ == "__main__":
    lobster = Lobster()
    results = lobster.run(max_pages=5)

    print(f"\n{'='*60}")
    print(f"昨日提取结果 ({len(results)} 条)")
    print(f"{'='*60}")
    for i, info in enumerate(results, 1):
        print(f"\n{i}. {info.chinese_name or '未命名'}")
        if info.foreign_name:
            print(f"   外文名: {info.foreign_name}")
        if info.director:
            print(f"   导演: {info.director}")
        if info.writer:
            print(f"   编剧: {info.writer}")
        if info.cast:
            print(f"   主演: {'/'.join(info.cast)}")
        if info.year:
            print(f"   年份: {info.year}")
        if info.awards:
            print(f"   获奖: {info.awards}")
        if info.rating:
            print(f"   评级: {info.rating}")
        if info.category:
            print(f"   类别: {info.category}")
        if info.language or info.subtitle:
            print(f"   语言: {info.language or ''}{info.subtitle or ''}")
        if info.season:
            print(f"   季数: 第{info.season}季")
        if info.episodes:
            print(f"   集数: 全{info.episodes}集")
        if info.source_link:
            print(f"   链接: {info.source_link}")
        print(f"   文件名: {info.generate_filename()}")
