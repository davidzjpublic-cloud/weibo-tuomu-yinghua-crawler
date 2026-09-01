# -*- coding: utf-8 -*-
"""
影视信息提取器
"""

import logging
import re
from typing import List, Optional, Tuple

from config import (
    AWARDS_PATTERNS,
    CAST_CLEAN_PREFIX_KEYWORDS,
    CHINESE_NUMBERS,
    FILM_FESTIVAL_KEYWORDS,
    GENRES,
    INVALID_CAST_KEYWORDS,
    INVALID_DIRECTOR_KEYWORDS,
    INVALID_WRITER_KEYWORDS,
    LANGUAGE_NAMES,
    MOVIE_KEYWORDS,
    NON_MOVIE_KEYWORDS,
    NON_RESOURCE_KEYWORDS,
    PATTERNS,
    RATING_PATTERNS,
    RESOURCE_HINT_KEYWORDS,
    SLASH_REPLACEMENTS,
    SUBTITLE_PATTERNS,
)
from models import MovieInfo

logger = logging.getLogger(__name__)


class MovieExtractor:
    """从微博文本中提取影视信息。"""

    def __init__(self) -> None:
        self.patterns = PATTERNS
        self.categories = GENRES
        self.awards_patterns = AWARDS_PATTERNS
        self.rating_patterns = RATING_PATTERNS
        self.subtitle_patterns = SUBTITLE_PATTERNS
        self.language_names = LANGUAGE_NAMES
        self.slash_replacements = SLASH_REPLACEMENTS
        self.chinese_numbers = CHINESE_NUMBERS
        # 语言匹配单元 = 基础语言名 + 斜杠替换生成的组合（如“瑞典德语”），
        # 按长度降序，避免组合被拆成短语言丢失前半部分
        self._lang_units = sorted(
            set(self.language_names) | set(self.slash_replacements.values()),
            key=len,
            reverse=True,
        )

    def _resolve_lang_part(self, lang_part: str) -> Optional[str]:
        """解析字幕词前的语言片段，斜杠/顿号组合去分隔符后照抄原文连写。

        无法解析为已知语言时返回 None，避免把人名列表等无关前文误当作语言。
        """
        if not lang_part:
            return None
        if lang_part.startswith('已出'):
            # “已出英/法语中字”的“已出”是状态词（字幕已出），不属于语言名
            lang_part = lang_part[2:]
        if '/' not in lang_part and '、' not in lang_part:
            if (
                lang_part in self._lang_units
                or lang_part.endswith('语')
                or lang_part in ('默片', '无对白')
            ):
                return lang_part
            return None
        parts = re.split(r'[/、]+', lang_part)
        resolved = []
        for seg in parts:
            if (
                seg in self._lang_units
                or seg + '语' in self._lang_units
                or seg.endswith('语')
            ):
                # 与 SLASH_REPLACEMENTS 表风格一致：各段照抄原文，
                # 不把“挪威”补成“挪威语”、“英”补成“英语”
                resolved.append(seg)
            else:
                return None
        return ''.join(resolved)

    def is_non_movie_content(self, text: str) -> bool:
        """判断文本是否不属于影视资源内容。"""
        if not text:
            return True

        for kw in NON_RESOURCE_KEYWORDS:
            if kw in text:
                return True

        if "《" in text and "》" in text:
            # 标题（书名号内）中的关键词不算非影视信号，
            # 如《悲惨世界:十周年纪念演唱会》片名本身含“周年”
            text_outside_title = re.sub(r'《[^》]*》', '', text)
            for keyword in ["今天是", "周年", "去世", "生日", "票房已破"]:
                if keyword in text_outside_title:
                    return True
            has_resource_hint = any(kw in text for kw in RESOURCE_HINT_KEYWORDS)
            has_film_festival = any(kw in text for kw in FILM_FESTIVAL_KEYWORDS)
            if has_resource_hint or has_film_festival:
                return False
            return False

        if "《" not in text:
            has_movie_keywords = any(kw in text for kw in MOVIE_KEYWORDS)
            if not has_movie_keywords:
                return True

        for keyword in NON_MOVIE_KEYWORDS:
            if keyword in text:
                return True

        return False

    def extract_name_pair(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """仅提取中文名和外文名，不做非影视过滤。"""
        if not text:
            return None, None

        names = re.findall(self.patterns["chinese_name"], text)
        if not names:
            return None, None

        chinese_name = names[0]
        foreign_name = self._extract_foreign_name(text, chinese_name, names)
        return chinese_name, foreign_name

    def _extract_foreign_name(
        self, text: str, chinese_name: str, all_names: List[str]
    ) -> Optional[str]:
        """根据中文名提取对应外文名。"""
        fn_match = re.search(
            r'《' + re.escape(chinese_name) + r'》\s*([（(])([^）)]+)([）)])',
            text,
        )
        if fn_match:
            return fn_match.group(2).strip()

        fn_match2 = re.search(
            r'《' + re.escape(chinese_name) + r'》\s*/\s*([^《》\s][^《》]{1,50})',
            text,
        )
        if fn_match2:
            return fn_match2.group(1).strip()

        if len(all_names) >= 2 and chinese_name in all_names:
            idx = all_names.index(chinese_name)
            if idx + 1 < len(all_names):
                candidate = all_names[idx + 1]
                if candidate and re.search(r'[a-zA-Z]', candidate):
                    # 拉丁字母占比过低时视为中文条目（如含少量数字的中文片名），
                    # 不作为外文名
                    total = max(len(candidate.replace(' ', '')), 1)
                    latin = len(re.findall(r'[a-zA-Z]', candidate))
                    if latin / total >= 0.3:
                        return candidate

        return None

    def _is_valid_role_name(self, name: str, role: str) -> bool:
        """校验人名是否适合指定角色。"""
        if not name or len(name) >= 15 or name.isdigit():
            return False
        if role == "director":
            invalid = INVALID_DIRECTOR_KEYWORDS
        elif role == "writer":
            invalid = INVALID_WRITER_KEYWORDS
        elif role == "cast":
            invalid = INVALID_CAST_KEYWORDS
        else:
            invalid = []
        return not any(kw in name for kw in invalid)

    def _extract_self_roles(self, text: str, info: MovieInfo) -> None:
        """处理自编自导自演 / 自导自演 / 自编自导 / 自编自演。"""
        patterns = [
            (r'([^《》\n\s]{2,15}?)自编自导自演', ["writer", "director", "cast"]),
            (r'([^《》\n\s]{2,15}?)自导自演', ["director", "cast"]),
            (r'([^《》\n\s]{2,15}?)自编自导', ["writer", "director"]),
            (r'([^《》\n\s]{2,15}?)自编自演', ["writer", "cast"]),
        ]

        for pattern, roles in patterns:
            for m in re.finditer(pattern, text):
                name = m.group(1).strip()
                pos = m.start()

                if not all(self._is_valid_role_name(name, role) for role in roles):
                    continue

                # 避免把角色词本身包含进人名（如“北野武自编”+“自导自演”）
                if any(kw in name for kw in ("编", "导", "演", "自")):
                    continue

                if "writer" in roles and not info.writer:
                    info.writer = name
                    info.writer_pos = pos
                if "director" in roles and not info.director:
                    info.director = name
                    info.director_pos = pos
                if "cast" in roles and name not in info.cast:
                    info.cast.append(name)
                    if info.cast_pos is None:
                        info.cast_pos = pos

    def extract(self, text: str, weibo_id: str = None, publish_time: str = None) -> Optional[MovieInfo]:
        """从微博文本提取影视信息。"""
        if self.is_non_movie_content(text):
            logger.info(f"非影视内容，跳过: {text[:30]}...")
            return None

        info = MovieInfo(raw_text=text, weibo_id=weibo_id, publish_time=publish_time)

        if not text:
            return info

        # 提取中文名和外文名
        info.chinese_name, info.foreign_name = self.extract_name_pair(text)

        # 处理自编自导自演等组合角色
        self._extract_self_roles(text, info)

        # 提取导演（组合角色未覆盖时再单独提取）
        if not info.director:
            director_candidates = []
            director_positions = []
            # “导演”与“剧集作品”等类型词之间可夹类型形容（如“三宅唱导演恐怖剧集作品”）
            genre_alt = '|'.join(re.escape(g) for g in self.categories)
            for m in re.finditer(
                rf'([^《》\n\s]{{2,15}}?)导演(?:(?:高分|热门|冷门)?(?:{genre_alt})?(?:电影|剧集|纪录片|动画)?作品|作品|电影|剧集|纪录片|动画|推荐|全\d+集|第\d+季|\s|$)',
                text,
            ):
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
                if (
                    len(cand) < 15
                    and not any(kw in cand for kw in INVALID_DIRECTOR_KEYWORDS)
                    and not cand.isdigit()
                ):
                    if best_director is None or len(cand) > len(best_director):
                        best_director = cand
                        best_director_pos = director_positions[i]
            if best_director:
                info.director = best_director
                info.director_pos = best_director_pos

        # 提取监制（如“侯孝贤监制 萧雅全导演作品”中的“侯孝贤”）
        if not info.supervisor:
            for m in re.finditer(r'([^《》\n\s]{2,15}?)监制', text):
                cand = m.group(1).strip()
                if (
                    len(cand) < 15
                    and not any(kw in cand for kw in INVALID_DIRECTOR_KEYWORDS)
                    and not cand.isdigit()
                ):
                    info.supervisor = cand
                    info.supervisor_pos = m.start()
                    break

        # 提取编剧（组合角色未覆盖时再单独提取）
        if not info.writer:
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
                if (
                    len(cand) < 15
                    and not any(kw in cand for kw in INVALID_WRITER_KEYWORDS)
                    and not cand.isdigit()
                ):
                    if best_writer is None or len(cand) > len(best_writer):
                        best_writer = cand
                        best_writer_pos = writer_positions[i]
            if best_writer:
                info.writer = best_writer
                info.writer_pos = best_writer_pos

        # 提取主演（组合角色已添加的，此处补充更多演员）
        cast_candidates = []

        for m in re.finditer(
            r'([^《》\n\s]{2,15}(?:[/、，,][^《》\n\s]{2,15})*)\s*(?:主演|出演)',
            text,
        ):
            cast_candidates.append(m.group(1).strip())

        cast_match2 = re.search(
            r'(?:主演|出演)[:：]\s*([^《》\n]{2,40}?)(?:\s|，|,|/|、|$)',
            text,
        )
        if cast_match2:
            cast_candidates.append(cast_match2.group(1).strip())

        for m in re.finditer(r'》\s*([^《》\n]{2,30}?)\s*(?:主演|出演)', text):
            cast_candidates.append(m.group(1).strip())

        all_cast: List[str] = []
        best_cast_pos = None
        for raw in cast_candidates:
            raw = re.sub(r'\s*(主演|出演)$', '', raw).strip()
            raw = re.sub(
                r'^(' + '|'.join(CAST_CLEAN_PREFIX_KEYWORDS) + r')',
                '',
                raw,
            ).strip()
            cast_list = [
                c.strip()
                for c in re.split(r'[/、，,\s]+', raw)
                if c.strip() and len(c.strip()) > 1 and len(c.strip()) < 15
            ]
            cast_list = [
                c
                for c in cast_list
                if not any(kw in c for kw in INVALID_CAST_KEYWORDS)
                and not c.isdigit()
                and '导演' not in c
                and '执导' not in c
                and not re.search(r'全\d+集|第\d+季', c)
            ]
            for c in cast_list:
                if c not in all_cast:
                    all_cast.append(c)
            if all_cast and best_cast_pos is None:
                pos = (
                    text.find(raw + '主演')
                    if raw + '主演' in text
                    else text.find(raw + '出演')
                )
                if pos == -1:
                    pos = text.find('主演') if '主演' in text else text.find('出演')
                best_cast_pos = pos if pos != -1 else None

        if all_cast:
            if not info.cast:
                info.cast = all_cast
                info.cast_pos = best_cast_pos
            else:
                # 组合角色已添加演员时，补充其他演员并去重
                for c in all_cast:
                    if c not in info.cast:
                        info.cast.append(c)
                if info.cast_pos is None:
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

        # 提取“X相关”描述（如“哈利·波特相关高分纪录片”中的“哈利·波特相关”），
        # 生成文件名时前缀到类别段最前
        related_match = re.search(r'([^《》\n，。：:\s]{1,20}相关)', text_after_title)
        if related_match:
            info.related_tag = related_match.group(1)

        # 提取出品方标注（如“A24出品科幻片”中的“A24出品”），
        # 生成文件名时作为独立段落置于获奖之后
        producer_match = re.search(r'([A-Za-z][A-Za-z0-9]{0,14}出品)', text_after_title)
        if producer_match:
            info.producer_tag = producer_match.group(1)

        # 提取“X作品”主创署名（如“佩德罗·阿莫多瓦作品”，不带“导演/执导”字样的署名），
        # 生成文件名时排在导演/主演之后、获奖之前；
        # 含角色词或奖项词的“X作品”（如“X导演作品”“XX奖提名作品”“自导自演作品”）跳过
        for m in re.finditer(r'([^《》\n，。：:\s]{2,15}作品)', text_after_title):
            credit = m.group(1)
            if any(
                kw in credit
                for kw in (
                    '导演', '执导', '编剧', '主演', '自导', '自编',
                    '获奖', '提名', '入围', '展映', '奖', '出品', '改编',
                    '电影', '剧集', '纪录', '动画', '短片', '遗作', '首作',
                )
            ):
                continue
            info.work_credit = credit
            break

        # 提取“X版”版本署名（如同一原著多版影视中的“鳄渊晴子版”，以演员名区分版本），
        # 生成文件名时作为独立段落置于获奖之后；
        # “完整版”“修复版”“真人版”“剧场版”“2024版”等通用版本词与纯数字跳过
        for m in re.finditer(r'([^《》\n，。：:\s]{2,15}?)版(?=\s|$)', text_after_title):
            credit = m.group(1)
            if credit.isdigit():
                continue
            if any(
                kw in credit
                for kw in (
                    '完整', '修复', '高清', '原声', '中文', '国语', '重制',
                    '蓝光', '加长', '终极', '未删', '正片', '纯享', '黑白',
                    '彩色', '精修', '真人', '剧场', '电影', '动画', '纪录',
                    '导演', '编剧', '主演', '出演', '改编', '语', '字', '版',
                )
            ):
                continue
            info.version_credit = m.group(0)
            break

        # 提取获奖情况
        found_awards = []
        for pattern in self.awards_patterns:
            match = re.search(pattern, text)
            if match:
                award_text = match.group(1)
                # “最佳X奖获奖/提名”中“奖”与“获奖/提名”语义重复，按惯例去掉
                # （如“柏林电影节最佳纪录片奖获奖作品”→“柏林电影节最佳纪录片获奖作品”）；
                # 不影响“金贝壳奖获奖作品”这类奖项名本身以“奖”结尾的形式
                award_text = re.sub(r'(最佳[^，。\s]{1,8}?)奖(获奖|提名)', r'\1\2', award_text)
                # “纽约影评人协会奖”按基准惯例不保留“奖”字（与“金马最佳”同风格；
                # 注意“美国国家影评人协会奖”仍保留“奖”，二者不共用此规则）
                award_text = award_text.replace('纽约影评人协会奖', '纽约影评人协会')
                if not any(
                    award_text in existing and award_text != existing
                    for existing in found_awards
                ):
                    found_awards = [
                        existing for existing in found_awards if existing not in award_text
                    ]
                    found_awards.append(award_text)
        if found_awards:
            info.awards = ' '.join(found_awards)

        # 提取改编信息
        adaptation_match = re.search(r'(改编自[^《》]{0,20}《[^》]+》)', text)
        if not adaptation_match:
            adaptation_match = re.search(
                r'(改编自[^《》\n]{0,30}?(?:原著(?:小说)?|小说|漫画|游戏|叙事诗)(?:\s*\d{4}版)?)',
                text,
            )
        if adaptation_match:
            adaptation_text = adaptation_match.group(1).replace('\n', ' ').strip()
            if info.awards:
                info.awards = adaptation_text + ' ' + info.awards
            else:
                info.awards = adaptation_text

        # 奖项/改编片段之外的正文（评级、类别的独立用法在这里判断）
        non_award_text = text
        if info.awards:
            for piece in info.awards.split(' '):
                if piece:
                    non_award_text = non_award_text.replace(piece, ' ')

        # 提取评级
        found_ratings = []
        for pattern in self.rating_patterns:
            match = re.search(pattern, text)
            if match:
                rating_text = match.group(1)
                if info.awards and rating_text in info.awards:
                    # 奖项/改编文本已含同一评级词（如“高分原著”“热门高分原著”）时
                    # 默认不重复显示（龙纹身的女孩；英国国王：“导演高分作品”）；
                    # 但奖项之外的正文另有独立评级用法——“高分+类型词”而非
                    # “高分作品”（异乡人：“主演高分传记片”）——时仍显示
                    if not re.search(
                        re.escape(rating_text) + r'(?!原著|作品)', non_award_text
                    ):
                        continue
                if any(
                    rating_text in existing and rating_text != existing
                    for existing in found_ratings
                ):
                    continue
                found_ratings = [
                    existing for existing in found_ratings if existing not in rating_text
                ]
                found_ratings.append(rating_text)
        if found_ratings:
            info.rating = ' '.join(found_ratings)

        # 提取语言和字幕：遍历每个字幕词的所有出现位置，
        # 取第一个能解析出语言的位置，避免文中其他位置的同一字幕词干扰
        lang_matched = False
        for sub_pat in self.subtitle_patterns:
            start = 0
            while True:
                sub_idx = text.find(sub_pat, start)
                if sub_idx == -1:
                    break
                before = text[:sub_idx].rstrip()

                # 预处理斜杠分隔的组合语言
                original_before = before
                for old, new in sorted(
                    self.slash_replacements.items(), key=lambda x: len(x[0]), reverse=True
                ):
                    before = before.replace(old, new)

                # 仅当紧邻字幕词的最后一个词本身含斜杠/顿号时才按组合语言解析；
                # 前文其他位置（如主演名单“唐泽寿明/芦田爱菜”）出现斜杠与此无关
                last_word = original_before.split()[-1] if original_before.split() else ''
                if '/' in last_word or '、' in last_word:
                    lang_part = before.split()[-1] if before.split() else ''
                    resolved = self._resolve_lang_part(lang_part)
                    if resolved:
                        info.language = resolved
                        info.subtitle = sub_pat
                        lang_matched = True

                if not lang_matched:
                    found_langs = []
                    temp = before

                    # 优先匹配长组合语言（_lang_units 已按长度降序）
                    while temp:
                        matched = False
                        for unit in self._lang_units:
                            if temp.endswith(unit):
                                found_langs.append(unit)
                                temp = temp[:-len(unit)].rstrip()
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

                if lang_matched:
                    break
                start = sub_idx + 1
            if lang_matched:
                break

        if not lang_matched:
            lang_match = re.search(self.patterns["language_subtitle"], text)
            if lang_match:
                info.language = lang_match.group(1)
                info.subtitle = lang_match.group(2)
            else:
                fallback = re.search(
                    r'(中英双语|中英双字|中文字幕|中字|双语字幕|中英字幕|内嵌中字|外挂中字|中日双字)',
                    text,
                )
                if fallback:
                    info.subtitle = fallback.group(1)

        # “无对白纯享”这类纯风光/音乐片说明（不附带字幕词），作为语言位置保留
        if not info.language:
            pure_match = re.search(r'(无对白纯享)', text)
            if pure_match:
                info.language = pure_match.group(1)

        # 提取集数
        ep_match = re.search(self.patterns["episodes"], text)
        if ep_match:
            ep_str = ep_match.group(1)
            if ep_str in self.chinese_numbers:
                info.episodes = self.chinese_numbers[ep_str]
            else:
                try:
                    info.episodes = int(ep_str)
                except ValueError:
                    pass

        # 综艺“期”数（如“全13期”），保留“期”单位存入季集段
        qi_match = re.search(r'全([0-9一二两三四五六七八九十]+)期', text)
        if qi_match:
            qi_str = qi_match.group(1)
            qi_num = self.chinese_numbers.get(qi_str)
            if qi_num is None:
                try:
                    qi_num = int(qi_str)
                except ValueError:
                    qi_num = None
            if qi_num is not None:
                info.season_extra = f'全{qi_num}期'

        # 提取季数
        season_match = re.search(self.patterns["season"], text)
        if season_match:
            raw = season_match.group(0)
            info.season_raw = re.sub(r'季+$', '', raw)
            season_str = season_match.group(1)
            if season_str in self.chinese_numbers:
                info.season = self.chinese_numbers[season_str]
                # 只在"全"开头时替换为阿拉伯数字，"第"开头保留中文
                if info.season_raw.startswith('全'):
                    info.season_raw = info.season_raw.replace(season_str, str(info.season))
            else:
                try:
                    info.season = int(season_str)
                except ValueError:
                    pass

        # 提取额外季数信息
        extra_season_patterns = [
            r'(全\d+部)',
            r'(全\d+季\+番外\+花絮)',
            r'(全\d+季\+电影)',
            r'(第[一二两三四五六七八九十\d]+季(?:首播至第[一二两三四五六七八九十\d]+集)?(?:\s+含中字(?:前|第)[一二两三四五六七八九十\d]+季|\s+含[^\n，。:：]{0,8}?第[一二两三四五六七八九十\d]+季)?)',
            # 无季数、只有“首播至第X集/期”的连载状态（如 绿灯军团）
            r'(首播至第[一二两三四五六七八九十\d]+[集期])',
        ]
        for pattern in extra_season_patterns:
            extra_season = re.search(pattern, text)
            if extra_season:
                captured = extra_season.group(1)
                # “全N部”直接作为季数/部数信息保留
                if re.match(r'^全\d+部$', captured):
                    info.season_extra = captured
                    break
                # 仅当捕获到除“第X季”之外的附加信息时才使用
                if '首播' in captured or '含' in captured or '番外' in captured or '+电影' in captured:
                    info.season_extra = captured.replace('\n', ' ')
                    # “含中英双字第一季”这类含语言/字幕的附带季说明，
                    # 语言已单独提取，改写为“含第一季”（“含中字第X季”惯用语原样保留）
                    info.season_extra = re.sub(
                        r'含(?!中字)\S{0,8}?第([一二两三四五六七八九十\d]+季)',
                        r'含第\1',
                        info.season_extra,
                    )
                    # 综艺“期”数用阿拉伯数字（如“首播至第五期”→“首播至第5期”）；
                    # “集”保持原样中文数字（如绿灯军团“首播至第一集”）
                    m = re.match(r'^(首播至第)([一二两三四五六七八九十\d]+)(期)$', info.season_extra)
                    if m and m.group(2) in self.chinese_numbers:
                        info.season_extra = m.group(1) + str(self.chinese_numbers[m.group(2)]) + m.group(3)
                    break

        # 提取年份
        year_match = re.search(self.patterns["year"], text)
        if year_match:
            info.year = int(year_match.group(0))

        # 判断类型
        if "动画" in text and "剧集" in text:
            info.genre = "动画剧集"
        elif re.search(r'无对白(?:纪录片|短片|动画)', text):
            # “无对白+类型”连写作为整体类型（如无对白纪录片、无对白动画）；
            # “无对白纯享”这类不带类型词的不在此列，仍走语言位置
            info.genre = re.search(r'无对白(?:纪录片|短片|动画)', text).group(0)
        elif "纪录片" in text or "纪录长片" in text:
            info.genre = "纪录片"
        elif "纪录短片" in text:
            # “纪录短片”为组合类型词（如“高分纪录短片”），整体作为 genre
            info.genre = "纪录短片"
        elif "短片" in text:
            info.genre = "短片"
        elif "真人秀" in text:
            info.genre = "真人秀"
        elif "访谈节目" in text:
            info.genre = "访谈节目"
        elif "综艺" in text:
            # 综艺节目作为类型词（如“冷门高分综艺推荐”）
            info.genre = "综艺"
        elif "剧集" in text or re.search(
            '(?:' + '|'.join(
                re.escape(g) for g in self.categories if g not in ('音乐', '歌舞')
            ) + r')剧(?!情|场|照|本|终)', text
        ):
            # “悬疑剧”这类“类型+剧”连写视作剧集（伴人而生）；
            # 音乐剧/歌舞剧是电影类型而非剧集（玛蒂尔达：音乐剧），排除
            info.genre = "剧集"
        elif re.search(r'(?<![A-Za-z])SP(?![A-Za-z])', text):
            # 日剧/日综特别篇“SP”（如“治愈SP推荐”），作为类型替代默认“片”
            info.genre = "SP"
        elif "同影" in text:
            # 同性恋题材电影简称“同影”，作为类型词（如“冷门喜剧同影”）
            info.genre = "同影"
        elif "动画" in text:
            # 动画电影在文件名中显示为“动画片”，动画剧集已在上面的组合分支处理
            info.genre = "动画片" if "动画电影" in text else "动画"
        else:
            info.genre = "电影"

        # 类别词与获奖信息重复时不再作为类别显示（在类型判定后处理）：
        # “最佳剧情片”“金马最佳剧情短片”的类别词只出现在奖项文本内 → 抑制（曼克等）；
        # “最佳动画长片”中的“动画”即类型词本身 → 抑制；
        # “最佳剧情长片”中的“剧情”≠类型词，显示形式“剧情片”不在获奖中 → 保留（范保德）；
        # 正文奖项以外另有该类别词（主演行“喜剧动作犯罪片”+奖项“最佳喜剧片”）
        # → 保留（耐撕侦探）
        if info.category and info.awards:
            kept = []
            for c in info.category.split('/'):
                if (
                    c in info.awards
                    and (
                        c + '长片' not in info.awards
                        or (info.genre or '').startswith(c)
                    )
                    and c not in non_award_text
                ):
                    continue
                kept.append(c)
            info.category = '/'.join(kept) if kept else None

        return info
