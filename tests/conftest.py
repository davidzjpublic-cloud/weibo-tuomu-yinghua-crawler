# -*- coding: utf-8 -*-
"""
测试 fixture
"""

import pytest


@pytest.fixture
def sample_movie_weibo():
    """典型电影博文。"""
    return {
        "text": (
            "《肖申克的救赎》（The Shawshank Redemption）1994 弗兰克·德拉邦特导演 "
            "蒂姆·罗宾斯、摩根·弗里曼主演 国语中字 夸克资源 "
            "改编自斯蒂芬·金《四季奇谭》 高分经典 "
            "https://pan.quark.cn/s/abc123"
        ),
        "id": "1234567890",
        "created_at": "2026-08-12 10:00:00",
    }


@pytest.fixture
def sample_documentary_weibo():
    """纪录片博文，验证 genre 为纪录片且 category 去重。"""
    return {
        "text": (
            "《地球脉动》Planet Earth 2006 纪录片 自然 "
            "英语中英双字 全11集 高分 "
            "https://pan.quark.cn/s/doc456"
        ),
        "id": "1234567891",
        "created_at": "2026-08-12 11:00:00",
    }


@pytest.fixture
def sample_series_weibo():
    """剧集博文，验证季数和集数提取。"""
    return {
        "text": (
            "《绝命毒师》Breaking Bad 2008 文斯·吉里根导演 布莱恩·克兰斯顿主演 "
            "剧集 全5季 全62集 英语中英双字 "
            "https://pan.quark.cn/s/series789"
        ),
        "id": "1234567892",
        "created_at": "2026-08-12 12:00:00",
    }


@pytest.fixture
def sample_non_movie_weibo():
    """非影视资源博文，应被过滤。"""
    return {
        "text": "今天是《泰坦尼克号》上映27周年，回顾经典海报构图。",
        "id": "1234567893",
        "created_at": "2026-08-12 13:00:00",
    }


@pytest.fixture
def sample_language_edge_weibo():
    """斜杠分隔语言 edge case。"""
    return {
        "text": (
            "《寄生虫》Parasite 2019 奉俊昊导演 宋康昊主演 "
            "英/韩语中英双字 奥斯卡最佳影片获奖作品 "
            "https://pan.quark.cn/s/parasite012"
        ),
        "id": "1234567894",
        "created_at": "2026-08-12 14:00:00",
    }


@pytest.fixture
def sample_short_film_weibo():
    """短片博文。"""
    return {
        "text": (
            "《调音师》L'accordeur 2010 奥利维耶·特雷内导演 短片 法语中字 "
            "https://pan.quark.cn/s/short345"
        ),
        "id": "1234567895",
        "created_at": "2026-08-12 15:00:00",
    }


@pytest.fixture
def sample_invalid_cast_weibo():
    """含无效演员关键词的博文。"""
    return {
        "text": (
            "《测试片》Test Movie 2021 悬疑主演 高分导演 中字 "
            "https://pan.quark.cn/s/invalidcast"
        ),
        "id": "1234567896",
        "created_at": "2026-08-12 16:00:00",
    }
