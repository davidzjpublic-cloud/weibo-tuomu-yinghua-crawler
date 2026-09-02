# -*- coding: utf-8 -*-
"""
影视信息数据模型
"""

import html
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

from config import CHINESE_NUMBERS, FILENAME_INVALID_CAST_KEYWORDS, INVALID_DIRECTOR_KEYWORDS, INVALID_WRITER_KEYWORDS
from utils import safe_filename


@dataclass
class MovieInfo:
    """影视信息数据类。"""

    chinese_name: Optional[str] = None
    foreign_name: Optional[str] = None
    year: Optional[int] = None
    director: Optional[str] = None
    # “X监制”（如“侯孝贤监制”），生成文件名时按原文位置插入角色段
    supervisor: Optional[str] = None
    writer: Optional[str] = None
    cast: List[str] = field(default_factory=list)
    language: Optional[str] = None
    subtitle: Optional[str] = None
    genre: Optional[str] = None
    category: Optional[str] = None
    # “X相关”描述（如“哈利·波特相关”），生成文件名时前缀到类别段最前
    related_tag: Optional[str] = None
    # 出品方标注（如“A24出品”），生成文件名时作为独立段落置于获奖之后
    producer_tag: Optional[str] = None
    # “X作品”主创署名（如“佩德罗·阿莫多瓦作品”，不带“导演”字样），
    # 生成文件名时排在导演/主演之后、获奖之前
    work_credit: Optional[str] = None
    # “X版”版本署名（如同一原著多版影视中的“鳄渊晴子版”），
    # 生成文件名时作为独立段落置于获奖之后
    version_credit: Optional[str] = None
    rating: Optional[str] = None
    awards: Optional[str] = None
    douban_rating: Optional[str] = None
    season: Optional[int] = None
    season_raw: Optional[str] = None
    season_extra: Optional[str] = None
    episodes: Optional[int] = None
    source_link: Optional[str] = None
    quark_fid: Optional[str] = None
    quark_file_name: Optional[str] = None
    # 转存情况：True=已转存，False=未转存，None=未启用 --save
    saved: Optional[bool] = None
    weibo_id: Optional[str] = None
    publish_time: Optional[str] = None
    raw_text: Optional[str] = None
    director_pos: Optional[int] = None
    supervisor_pos: Optional[int] = None
    writer_pos: Optional[int] = None
    cast_pos: Optional[int] = None

    def __setattr__(self, name: str, value) -> None:
        # 片名字段统一归一化：去首尾空格，HTML 实体解码，半角冒号转为全角冒号，
        # 并去掉全角冒号两侧的空格，避免 "叶芝: 狂热的心" 变成 "叶芝： 狂热的心"
        if name in ("chinese_name", "foreign_name") and isinstance(value, str):
            value = html.unescape(value).strip().replace(":", "：")
            value = re.sub(r'\s*：\s*', '：', value)
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        if self.cast is None:
            self.cast = []
        # 数字字段统一转为 int 或 None
        for field_name in ("year", "season", "episodes"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, int):
                try:
                    setattr(self, field_name, int(value))
                except (ValueError, TypeError):
                    setattr(self, field_name, None)
        # 字符串字段去首尾空格（片名字段在 __setattr__ 中已额外归一化冒号）
        for field_name, value in self.__dict__.items():
            if isinstance(value, str):
                setattr(self, field_name, value.strip())

    def to_dict(self) -> dict:
        """转换为字典，便于 JSON 序列化。"""
        return asdict(self)

    def _build_role_parts(self) -> List[Tuple[int, str]]:
        """构建导演/编剧/主演片段，同一人多角色时合并为“自编自导自演”等。"""
        # 收集每个名字对应的角色及位置
        role_map: Dict[str, List[Tuple[str, int]]] = {}

        if self.cast:
            cast_pos = self.cast_pos if self.cast_pos is not None else 9999
            for name in self.cast:
                role_map.setdefault(name, []).append(("cast", cast_pos))

        if self.director:
            director_pos = self.director_pos if self.director_pos is not None else 9999
            role_map.setdefault(self.director, []).append(("director", director_pos))

        if self.writer:
            writer_pos = self.writer_pos if self.writer_pos is not None else 9999
            role_map.setdefault(self.writer, []).append(("writer", writer_pos))

        ordered_parts: List[Tuple[int, str]] = []
        combined_names: set = set()

        # 优先处理一人多角色的情况
        for name, roles in role_map.items():
            if len(roles) < 2:
                continue

            role_types = {r[0] for r in roles}
            if role_types == {"director", "cast"}:
                label = "自导自演"
            elif role_types == {"writer", "director"}:
                label = "自编自导"
            elif role_types == {"writer", "cast"}:
                label = "自编自演"
            elif role_types == {"writer", "director", "cast"}:
                label = "自编自导自演"
            else:
                continue

            pos = min(r[1] for r in roles)
            ordered_parts.append((pos, f"{safe_filename(name)}{label}"))
            combined_names.add(name)

        # 单独角色（去掉已合并的人名）
        if self.director and self.director not in combined_names:
            director_clean = self.director.strip()
            is_valid = (
                director_clean
                and len(director_clean) < 15
                and not any(kw in director_clean for kw in INVALID_DIRECTOR_KEYWORDS)
                and not director_clean.isdigit()
                and not re.search(r'全\d+集|第\d+季', director_clean)
            )
            if is_valid:
                pos = self.director_pos if self.director_pos is not None else 9999
                ordered_parts.append((pos, f"{safe_filename(director_clean)}导演"))

        if self.supervisor:
            supervisor_clean = self.supervisor.strip()
            is_valid = (
                supervisor_clean
                and len(supervisor_clean) < 15
                and not any(kw in supervisor_clean for kw in INVALID_DIRECTOR_KEYWORDS)
                and not supervisor_clean.isdigit()
                and not re.search(r'全\d+集|第\d+季', supervisor_clean)
            )
            if is_valid:
                pos = self.supervisor_pos if self.supervisor_pos is not None else 9999
                ordered_parts.append((pos, f"{safe_filename(supervisor_clean)}监制"))

        if self.writer and self.writer not in combined_names:
            writer_clean = self.writer.strip()
            is_valid = (
                writer_clean
                and len(writer_clean) < 15
                and not any(kw in writer_clean for kw in INVALID_WRITER_KEYWORDS)
                and not writer_clean.isdigit()
            )
            if is_valid:
                pos = self.writer_pos if self.writer_pos is not None else 9999
                ordered_parts.append((pos, f"{safe_filename(writer_clean)}编剧"))

        if self.cast:
            invalid_cast_keywords = FILENAME_INVALID_CAST_KEYWORDS
            cast_clean = [
                c for c in self.cast
                if c not in combined_names
                and len(c) < 15
                and c not in invalid_cast_keywords
                and not c.isdigit()
            ]
            if cast_clean:
                cast_str = '、'.join(cast_clean[:4])
                # 超过 4 人截断后加“等”（“A、B、C、D等主演”）
                cast_suffix = '等主演' if len(cast_clean) > 4 else '主演'
                pos = self.cast_pos if self.cast_pos is not None else 9999
                ordered_parts.append((pos, f"{safe_filename(cast_str)}{cast_suffix}"))

        ordered_parts.sort(key=lambda x: x[0])
        return ordered_parts

    def generate_filename(self) -> str:
        """按格式生成文件名：中文名 外文名 年份（主演 导演 编剧 获奖 评级类别类型 季数集数 语言字幕）"""
        parts = []

        # 处理标题末尾的季节数字，如《杀人者的购物中心2》+ 全两季 -> 杀人者的购物中心 1-2季
        title_season = None
        season_indicators_present = False
        name = ""
        if self.chinese_name:
            name = safe_filename(self.chinese_name)
            if self.season is not None and 1 <= self.season <= 9 and self.raw_text:
                # 构建该季数对应的中文数字列表（如 3 -> ['三']）
                season_chinese_nums = [
                    ch for ch, n in CHINESE_NUMBERS.items() if n == self.season
                ]
                # 仅当原文同时出现”全N季/全X季”等季节描述时才拆分，避免误拆《9号秘事》这类片名
                indicators = [f'全{self.season}季']
                indicators.extend(f'全{ch}季' for ch in season_chinese_nums)
                season_indicators_present = any(ind in self.raw_text for ind in indicators)
                if season_indicators_present:
                    # 1) 末尾阿拉伯数字
                    m = re.search(r'(\d)\s*$', name)
                    if m and int(m.group(1)) == self.season:
                        title_season = self.season
                        name = name[:m.start()].rstrip()
                    else:
                        # 2) 末尾中文数字，可带”季”，如”切尔西侦探三季”
                        for ch in season_chinese_nums:
                            m = re.search(re.escape(ch) + r'(?:季)?\s*$', name)
                            if m:
                                title_season = self.season
                                name = name[:m.start()].rstrip()
                                break
            parts.append(name)

        # 待追加的季数范围（标题含季数字 或 正文有全N季描述）
        season_range = None
        if name:
            if title_season is not None:
                season_range = f"1-{title_season}季"
            elif (
                season_indicators_present
                and self.season is not None
                and 1 <= self.season <= 9
            ):
                # 标题本身没有季节后缀，但正文有全N季描述，也补成 1-N季
                season_range = f"1-{self.season}季"

        if self.foreign_name:
            foreign = safe_filename(self.foreign_name)
            if season_range:
                # 外文名自带季数后缀（如“Екатерина Сезон 1”）时，
                # 去掉末尾数字与“1-N季”合并为“Сезон 1-N季”
                foreign = re.sub(r'(Сезон|Season)\s*\d+\s*$', r'\1', foreign).rstrip()
            parts.append(foreign)

        if season_range:
            parts.append(season_range)

        if self.year:
            # 标题或改编/获奖信息中已含年份时不再重复追加
            year_str = str(self.year)
            title_text = f"{self.chinese_name or ''}{self.foreign_name or ''}{self.awards or ''}"
            if year_str not in title_text:
                parts.append(year_str)

        bracket_parts = []
        # 奖项末尾的类型词是否已剥离（剥离后 genre 改为独立显示）
        genre_stripped_from_awards = False

        # 改编自类信息放在导演/主演之前；
        # awards 同时含“改编自”与其他奖项时（斯万的爱情）拆开：
        # “改编自”前置，其余奖项仍按奖项位置排在角色之后
        adaptation_part = None
        awards_rest = self.awards
        if self.awards and self.awards.startswith('改编自'):
            award_split = self.awards.split(' ', 1)
            adaptation_part = award_split[0]
            awards_rest = award_split[1] if len(award_split) > 1 else None
        if adaptation_part:
            bracket_parts.append(safe_filename(adaptation_part))

        ordered_parts = self._build_role_parts()
        bracket_parts.extend([p[1] for p in ordered_parts])

        # “X作品”主创署名排在角色之后、获奖之前
        if self.work_credit:
            bracket_parts.append(safe_filename(self.work_credit))

        if awards_rest:
            awards_clean = safe_filename(awards_rest)
            # 若奖项末尾与类型重复（如“洛迦诺电影节展映纪录片”+ genre“纪录片”），去掉末尾类型词；
            # 泛型“电影”除外——“十佳独立电影”的“电影”是荣誉名一部分，保留（松林外）
            if self.genre and self.genre != "电影" and awards_clean.endswith(self.genre):
                awards_clean = awards_clean[:-len(self.genre)].rstrip()
                genre_stripped_from_awards = True
            # 奖项文本中的半角“/”全角化（金球奖最佳限定剧/电视电影），
            # 与夸克重命名后的目录名保持一致；片名中的“/”不受影响（19/20 成年初体验）
            bracket_parts.append(awards_clean.replace('/', '／'))

        # “X版”版本署名独立成段，置于获奖之后、出品方之前
        if self.version_credit:
            bracket_parts.append(safe_filename(self.version_credit))

        # 出品方标注独立成段，置于获奖之后、类别之前（与奖项以空格分隔）
        if self.producer_tag:
            bracket_parts.append(safe_filename(self.producer_tag))

        combined = []
        if self.related_tag:
            # “X相关”描述置于类别段最前（如“哈利·波特相关高分纪录片”）
            combined.append(safe_filename(self.related_tag))
        if self.rating:
            combined.append(safe_filename(self.rating))
        # 当 genre 为 "短片" 时，category 不显示（避免与奖项中的"短片"重复）
        if self.category and not (self.genre == "短片" and self.category == "短片"):
            cat_parts = [c for c in self.category.split('/') if c]
            # 过滤掉与 genre 有包含/被包含关系的部分，避免"纪录"+"纪录片"="纪录纪录片"；
            # genre 为“短片”且奖项未提及“短片”时保留“短片”部分（“科幻动画短片”整体显示）
            keep_genre_dup = self.genre == "短片" and not (self.awards and "短片" in self.awards)
            filtered = [c for c in cat_parts if not (self.genre and not keep_genre_dup and (c in self.genre or self.genre in c))]
            if filtered:
                combined.append(''.join(filtered))
        # genre 显示条件（“无对白X”类整体类型词始终显示，如“无对白动画”；
        # 奖项末尾的类型词已被剥离时 genre 单独显示，如“圣丹斯电影节展映 纪录片”）
        show_genre = self.genre and (self.rating or self.category or self.genre.startswith("无对白") or genre_stripped_from_awards or (self.genre in ("剧集", "动画剧集") and (self.season or self.episodes or self.season_extra)))
        # category 已包含 genre 时不重复
        if show_genre and self.category and self.genre in self.category.replace('/', ''):
            show_genre = False
        # 短片不显示 genre
        if show_genre and self.genre == "短片":
            show_genre = False
        # 奖项本身已含“纪录”且无额外评级时，不再重复显示 genre
        # （含“纪录长片”这类变体，如“奥斯卡最佳纪录长片获奖作品”；
        # 末尾“纪录片”已被剥离进 genre 的情形除外）
        if (
            show_genre
            and self.genre == "纪录片"
            and self.awards
            and "纪录" in self.awards
            and not self.rating
            and not genre_stripped_from_awards
        ):
            show_genre = False
        if show_genre and self.genre:
            if self.genre == "电影":
                if self.raw_text and "电影系列" in self.raw_text:
                    # 系列合集保留“电影系列”原样（如 恐惧街）
                    combined.append("电影系列")
                elif self.category and "夏日" in self.category:
                    # “夏日电影”是惯用搭配，保留“电影”二字（如 盛夏的时光）
                    combined.append("电影")
                else:
                    # 电影在文件名中显示为“片”，与微博原文风格一致
                    combined.append("片")
            else:
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
                # “中文字幕”是完整词，与语言之间保留空格（如“默片 中文字幕”）
                if self.subtitle == '中文字幕' and self.language:
                    lang_str += ' ' + self.subtitle
                else:
                    lang_str += self.subtitle
            bracket_parts.append(safe_filename(lang_str))

        # 豆瓣评分放在括号内最后（文件名最后的右括号前）
        if self.douban_rating:
            bracket_parts.append(safe_filename(self.douban_rating))

        if bracket_parts:
            parts.append(f"（{' '.join(bracket_parts)}）")

        return " ".join(parts) if parts else "未命名"
