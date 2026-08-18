# -*- coding: utf-8 -*-
"""
通用工具函数
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional, Union

from dateutil import parser as date_parser

from config import DATE_FORMATS

logger = logging.getLogger(__name__)


def safe_filename(text: Optional[str]) -> str:
    """将字符串处理为安全的文件名片段。

    移除 Windows 非法字符，将英文冒号替换为中文冒号，并去除首尾空格。
    """
    if not text:
        return ""
    text = re.sub(r'[<>"/\\|?*]', '', str(text))
    text = text.replace(':', '：')
    # 去掉中文冒号两侧的空格，避免文件名中出现 "： " 这类间隔
    text = re.sub(r'\s*：\s*', '：', text)
    return text.strip()


def clean_html(text: str) -> str:
    """清理微博 HTML 文本：将 br 转为换行并移除其余标签。"""
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text


def get_publish_date(value: Union[str, int, float, None]) -> Optional[date]:
    """解析微博发布时间为 date 对象，无法解析时返回 None。

    支持字符串（dateutil 优先，再按 DATE_FORMATS）与 Unix 时间戳。
    """
    if value is None:
        return None

    # 处理 Unix 时间戳
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).date()
        except (OSError, ValueError, OverflowError) as e:
            logger.debug(f"时间戳解析失败: {value} - {e}")
            return None

    # 字符串格式：先尝试 dateutil，再尝试显式格式
    text = str(value).strip()
    if not text:
        return None

    try:
        return date_parser.parse(text).date()
    except (ValueError, TypeError, OverflowError):
        pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    logger.debug(f"无法解析发布时间: {text}")
    return None


def parse_publish_time(
    value: Union[str, int, float, None],
    target_date: Optional[str] = None,
) -> bool:
    """判断微博发布时间是否等于目标日期。

    Args:
        value: 微博发布时间，可能是字符串、Unix 时间戳或 None。
        target_date: 目标日期字符串，格式 "YYYY-MM-DD"。默认为昨天。

    Returns:
        是否为目标日期。无法解析时返回 False。
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 处理 "昨天" 字符串（相对时间，无法换算为绝对日期，单独比较）
    if isinstance(value, str) and "昨天" in value:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return target_date == yesterday

    d = get_publish_date(value)
    return d is not None and d.strftime("%Y-%m-%d") == target_date
