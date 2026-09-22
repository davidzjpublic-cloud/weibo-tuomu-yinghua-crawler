# -*- coding: utf-8 -*-
"""
豆瓣搜索模块单元测试
"""

import pytest

import douban
from douban import (
    _is_chinese,
    _is_latin_title,
    _is_minor_script,
    _fetch_douban_search,
    search_movie,
    search_movie_foreign_name,
    search_movie_rating,
)


@pytest.fixture(autouse=True)
def isolate_douban_cache(tmp_path, monkeypatch):
    """隔离豆瓣磁盘缓存：测试写入临时文件，避免污染真实 .douban_cache.json。

    同时重置限流短路标记（真实请求的集成测试可能置位，泄漏到后续用例）。
    """
    monkeypatch.setattr(douban, "CACHE_FILE", tmp_path / "douban_cache_test.json")
    douban._cache.clear()
    monkeypatch.setattr(douban, "_rexxar_search_blocked", False)
    yield
    douban._cache.clear()


class _StubSession:
    """把 Session.get 委托给 fake_get，供 monkeypatch 替换 douban._session。

    避免测试触达真实网络（会话懒初始化会访问 m.douban.com 首页）。
    """

    headers = {}

    def __init__(self, handler):
        self._handler = handler

    def get(self, url, **kwargs):
        return self._handler(url, **kwargs)


class TestIsChinese:

    def test_chinese_text(self):
        assert _is_chinese("肖申克的救赎") is True

    def test_english_text(self):
        assert _is_chinese("The Shawshank Redemption") is False

    def test_empty(self):
        assert _is_chinese("") is False


class TestFetchDoubanSearch:

    def test_fetch_known_movie(self):
        # 集成测试：真实请求豆瓣
        foreign_name, rating = _fetch_douban_search("贝尔法斯特天堂路")
        # 豆瓣可能有结果也可能无结果，但不应抛异常
        assert foreign_name is None or isinstance(foreign_name, str)
        assert rating is None or isinstance(rating, str)

    def test_fetch_empty(self):
        foreign_name, rating = _fetch_douban_search("")
        assert foreign_name is None
        assert rating is None


class TestSearchMovie:

    def test_search_returns_tuple(self, monkeypatch):
        monkeypatch.setattr(
            douban, "_fetch_douban_search", lambda name, year=None, hint_names=None: ("X", "8.0")
        )
        douban._cache.clear()
        result = search_movie("tuple_test")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == ("X", "8.0")

    def test_ignore_identical_chinese_name(self, monkeypatch):
        # 用 monkeypatch 模拟豆瓣返回与输入相同的中文名
        monkeypatch.setattr(
            douban, "_fetch_douban_search", lambda name, year=None, hint_names=None: (name, "9.7")
        )
        douban._cache.clear()
        foreign_name, rating = search_movie("测试同名")
        assert foreign_name is None
        assert rating == "9.7"

    def test_keep_different_chinese_name(self, monkeypatch):
        monkeypatch.setattr(
            douban, "_fetch_douban_search", lambda name, year=None, hint_names=None: ("另一个中文名", "8.5")
        )
        douban._cache.clear()
        foreign_name, rating = search_movie("测试名")
        assert foreign_name == "另一个中文名"
        assert rating == "8.5"

    def test_search_movie_foreign_name(self, monkeypatch):
        monkeypatch.setattr(
            douban, "_fetch_douban_search", lambda name, year=None, hint_names=None: ("Test Name", "7.0")
        )
        douban._cache.clear()
        assert search_movie_foreign_name("foreign_name_test") == "Test Name"

    def test_search_movie_rating(self, monkeypatch):
        monkeypatch.setattr(
            douban, "_fetch_douban_search", lambda name, year=None, hint_names=None: (None, "6.5")
        )
        douban._cache.clear()
        assert search_movie_rating("rating_test") == "6.5"

    def test_cache(self, monkeypatch):
        call_count = [0]

        def mock_fetch(name, year=None, hint_names=None):
            call_count[0] += 1
            return ("Mock", "5.0")

        monkeypatch.setattr(douban, "_fetch_douban_search", mock_fetch)
        douban._cache.clear()
        search_movie("cache_test")
        search_movie("cache_test")
        assert call_count[0] == 1

    def test_failure_not_cached(self, monkeypatch):
        """失败的查询结果 (None, None) 不应被缓存。"""
        call_count = [0]

        def mock_fetch(name, year=None, hint_names=None):
            call_count[0] += 1
            return (None, None)

        monkeypatch.setattr(douban, "_fetch_douban_search", mock_fetch)
        douban._cache.clear()
        assert search_movie("fail_test") == (None, None)
        assert search_movie("fail_test") == (None, None)
        assert call_count[0] == 2
        assert "fail_test" not in douban._cache


class TestMinorScriptLatinPreference:
    """小语种文字标题自动改用拉丁字母“又名”，大语种保留原文。

    回归案例：然后我们跳了舞（格鲁吉亚文 და ჩვენ ვიცეკვეთ → And Then
    We Danced）、魂歌（缅甸文 လိပ်ပြာလင်္ကာ → Song of Souls）。
    """

    def test_minor_script_detection(self):
        assert _is_minor_script("და ჩვენ ვიცეკვეთ") is True   # 格鲁吉亚文
        assert _is_minor_script("လိပ်ပြာလင်္ကာ") is True          # 缅甸文
        # 大语种保留原文
        assert _is_minor_script("地面師たち") is False              # 日文
        assert _is_minor_script("슈룹") is False                    # 韩文
        assert _is_minor_script("คดีชมพู่") is False               # 泰文
        assert _is_minor_script("Екатерина Сезон 1") is False      # 俄文
        assert _is_minor_script("攝氏零度·春光再現") is False        # 中文
        assert _is_minor_script("And Then We Danced") is False     # 拉丁
        assert _is_minor_script("Café Society") is False           # 拉丁变音
        assert _is_minor_script("") is False

    def test_latin_title_detection(self):
        assert _is_latin_title("And Then We Danced") is True
        assert _is_latin_title("Da chven vitsek'vet") is True
        assert _is_latin_title("Café Society") is True
        assert _is_latin_title("以你的舞步撩动我(港)") is False      # 中文 aka
        assert _is_latin_title("2:1") is False                     # 无字母
        assert _is_latin_title("") is False

    @staticmethod
    def _fake_session(monkeypatch, original_title, aka_list, sid="30394484"):
        """构造 rexxar 搜索 + 条目详情响应，返回详情请求计数。

        搜索条目的中文标题固定为查询名（rexxar API 的 title 即中文标题，
        外文名 original_title 由详情接口返回）。
        """
        detail_calls = [0]

        class FakeResp:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def json(self):
                return self._payload

        search_payload = {
            "total": 1,
            "items": [
                {
                    "layout": "subject",
                    "target_type": "movie",
                    "target": {
                        "id": sid,
                        "title": "然后我们跳了舞",
                        "year": "2019",
                        "rating": {"count": 15856, "value": 7.8},
                        "card_subtitle": "瑞典 格鲁吉亚 / 剧情 / 列万·阿金",
                    },
                }
            ],
        }

        def fake_get(url, *args, **kwargs):
            if "rexxar/api/v2/search/movie" in url:
                return FakeResp(search_payload)
            if "subject_suggest" in url:
                return FakeResp([])
            if "rexxar/api/v2/movie/" in url:
                detail_calls[0] += 1
                return FakeResp(
                    {"title": "然后我们跳了舞", "original_title": original_title,
                     "aka": aka_list}
                )
            raise AssertionError(f"意外请求: {url}")

        monkeypatch.setattr(douban, "_session", _StubSession(fake_get))
        douban._last_request_time = 0.0
        return detail_calls

    def test_minor_script_replaced_by_latin_aka(self, monkeypatch):
        calls = self._fake_session(
            monkeypatch,
            "და ჩვენ ვიცეკვეთ",
            ["以你的舞步撩动我(港)", "And Then We Danced", "Da chven vitsek'vet"],
        )
        foreign, rating = _fetch_douban_search("然后我们跳了舞", 2019)
        assert foreign == "And Then We Danced"
        assert rating == "7.8"
        assert calls[0] == 1

    def test_no_latin_aka_keeps_native_title(self, monkeypatch):
        calls = self._fake_session(monkeypatch, "လိပ်ပြာလင်္ကာ", ["灵魂乐"])
        foreign, rating = _fetch_douban_search("然后我们跳了舞")
        assert foreign == "လိပ်ပြာလင်္ကာ"
        assert calls[0] == 1

    def test_major_script_keeps_original_title(self, monkeypatch):
        # 大语种（韩文）保留原文，不做拉丁替换；详情必然请求一次
        calls = self._fake_session(monkeypatch, "슈룹", ["And Then We Danced"])
        foreign, rating = _fetch_douban_search("然后我们跳了舞")
        assert foreign == "슈룹"
        assert calls[0] == 1

    def test_stale_minor_script_cache_refreshed(self, monkeypatch):
        """旧缓存中的小语种标题应被忽略并重查升级为拉丁标题。"""
        douban._cache["然后我们跳了舞"] = (("და ჩვენ ვიცეკვეთ", "7.8"), 0.0)
        self._fake_session(
            monkeypatch,
            "და ჩვენ ვიცეკვეთ",
            ["And Then We Danced"],
        )
        result = search_movie("然后我们跳了舞", 2019)
        assert result == ("And Then We Danced", "7.8")


class TestRexxarSearchFlow:
    """rexxar 搜索 API 流程：年份过滤、无结果、非 200 状态。

    年份为结构化字段，旧 www/search HTML 解析的误判隐患
    （海报 URL 数字、N人评当年份）已不存在。
    """

    @staticmethod
    def _fake(monkeypatch, items, detail=None):
        class FakeResp:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def json(self):
                return self._payload

        def fake_get(url, *args, **kwargs):
            if "rexxar/api/v2/search/movie" in url:
                return FakeResp({"total": len(items), "items": items})
            if "subject_suggest" in url:
                return FakeResp([])
            if "rexxar/api/v2/movie/" in url:
                return FakeResp(detail or {})
            raise AssertionError(f"意外请求: {url}")

        monkeypatch.setattr(douban, "_session", _StubSession(fake_get))
        douban._last_request_time = 0.0

    @staticmethod
    def _item(sid, title, year, rating, subtitle=""):
        return {
            "target_type": "movie",
            "target": {
                "id": sid,
                "title": title,
                "year": year,
                "rating": {"count": 100, "value": rating},
                "card_subtitle": subtitle,
            },
        }

    def test_year_filter_picks_matching_entry(self, monkeypatch):
        # 2022 美剧在前，2019 韩片在后；year=2019 应选中韩片条目
        self._fake(
            monkeypatch,
            items=[
                self._item("35410155", "监视者", "2022", 6.3, "美国 / 剧情 惊悚"),
                self._item("30442498", "监视者", "2019", 7.6, "韩国 / 惊悚 犯罪 / 韩石圭"),
            ],
            detail={"original_title": "왓쳐", "aka": ["Watcher"]},
        )
        foreign, rating = _fetch_douban_search("监视者", 2019)
        assert foreign == "왓쳐"
        assert rating == "7.6"

    def test_hint_names_use_card_subtitle(self, monkeypatch):
        # 同年同名条目，主演名在 card_subtitle 里甄别（合唱团事件）
        self._fake(
            monkeypatch,
            items=[
                self._item("37193250", "合唱团", "2025", 7.3,
                           "中国台湾 / 剧情 / 林孝谦 / 陈意涵"),
                self._item("36828836", "合唱团", "2025", 6.7,
                           "英国 / 剧情 / 尼古拉斯·希特纳 / 拉尔夫·费因斯"),
            ],
            detail={"original_title": "The Choral", "aka": []},
        )
        foreign, rating = _fetch_douban_search("合唱团", 2025, ["拉尔夫·费因斯"])
        assert foreign == "The Choral"
        assert rating == "6.7"

    def test_no_items_returns_none(self, monkeypatch):
        self._fake(monkeypatch, items=[])
        foreign, rating = _fetch_douban_search("不存在的片子")
        assert foreign is None
        assert rating is None

    def test_non_200_returns_none(self, monkeypatch):
        class FakeResp:
            status_code = 503
            text = ""

        monkeypatch.setattr(douban, "_session", _StubSession(lambda *a, **k: FakeResp()))
        douban._last_request_time = 0.0
        foreign, rating = _fetch_douban_search("监视者")
        assert foreign is None
        assert rating is None

    def test_detail_failure_keeps_rating(self, monkeypatch):
        # 详情请求失败时外文名为空，评分仍保留
        class FakeResp:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def json(self):
                return self._payload

        def fake_get(url, *args, **kwargs):
            if "rexxar/api/v2/search/movie" in url:
                return FakeResp({"total": 1, "items": [self._item("1", "疯神", "2021", 7.4)]})
            if "rexxar/api/v2/movie/" in url:
                return FakeResp({}, status_code=404)
            raise AssertionError(f"意外请求: {url}")

        monkeypatch.setattr(douban, "_session", _StubSession(fake_get))
        douban._last_request_time = 0.0
        foreign, rating = _fetch_douban_search("疯神", 2021)
        assert foreign is None
        assert rating == "7.4"

    def test_chinese_original_title_dropped_by_search_movie(self, monkeypatch):
        # 国产片 original_title 即中文名，search_movie 应丢弃外文名
        self._fake(
            monkeypatch,
            items=[self._item("1", "测试国产片", "2024", 8.0)],
            detail={"original_title": "测试国产片", "aka": []},
        )
        assert search_movie("测试国产片") == (None, "8.0")


class TestSuggestFallback:
    """rexxar 搜索被限流（403）时自动降级到 suggest 建议接口。"""

    @staticmethod
    def _fake(monkeypatch, suggest_items, detail):
        class FakeResp:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def json(self):
                return self._payload

        def fake_get(url, *args, **kwargs):
            if "rexxar/api/v2/search/movie" in url:
                return FakeResp({"msg": "need_login"}, status_code=403)
            if "subject_suggest" in url:
                return FakeResp(suggest_items)
            if "rexxar/api/v2/movie/" in url:
                return FakeResp(detail)
            if url.endswith("m.douban.com/"):
                return FakeResp("")
            raise AssertionError(f"意外请求: {url}")

        # 403 会触发主路重建会话（_session = None 后 _get_session() 建真会话
        # 并访问真实首页），钉住 _get_session 返回桩，保证测试不触网
        stub = _StubSession(fake_get)
        monkeypatch.setattr(douban, "_get_session", lambda: stub)
        monkeypatch.setattr(douban, "_rexxar_search_blocked", False)
        douban._last_request_time = 0.0

    @staticmethod
    def _suggest(sid, title, year, sub_title=""):
        return {
            "id": sid, "title": title, "sub_title": sub_title,
            "year": year, "type": "movie", "episode": "",
        }

    def test_403_falls_back_to_suggest(self, monkeypatch):
        self._fake(
            monkeypatch,
            suggest_items=[self._suggest("21770915", "冬眠", "2014", "Kış Uykusu")],
            detail={
                "title": "冬眠", "original_title": "Kış Uykusu",
                "year": "2014",
                "rating": {"count": 100, "value": 8.2},
                "directors": [{"name": "努里·比格·锡兰"}],
                "actors": [], "aka": [],
            },
        )
        foreign, rating = _fetch_douban_search("冬眠", 2014)
        assert foreign == "Kış Uykusu"
        assert rating == "8.2"
        # 连续 403 后主路置位短路，后续不再探测
        assert douban._rexxar_search_blocked is True

    def test_season_entry_uses_sub_title(self, monkeypatch):
        # 季类条目：original_title 带“Season N”后缀，外文名取 suggest 的 sub_title
        self._fake(
            monkeypatch,
            suggest_items=[
                self._suggest("37437665", "行尸走肉：死亡之城 第三季", "2026",
                              "The Walking Dead: Dead City"),
            ],
            detail={
                "title": "行尸走肉：死亡之城 第三季",
                "original_title": "The Walking Dead: Dead City Season 3",
                "year": "2026",
                "rating": {"count": 100, "value": 6.9},
                "directors": [], "actors": [], "aka": [],
            },
        )
        monkeypatch.setattr(douban, "_rexxar_search_blocked", True)
        foreign, rating = _fetch_douban_search("行尸走肉：死亡之城")
        assert foreign == "The Walking Dead: Dead City"
        assert rating == "6.9"

    def test_exact_title_sorted_first(self, monkeypatch):
        # 相关性把季条目排在主条目前时，同名主条目应排到最前
        self._fake(
            monkeypatch,
            suggest_items=[
                self._suggest("1", "测试剧 第二季", "2025", "Test S2"),
                self._suggest("2", "测试剧", "2023", "Test"),
            ],
            detail={
                "title": "测试剧", "original_title": "Test", "year": "2023",
                "rating": {"count": 1, "value": 7.0},
                "directors": [], "actors": [], "aka": [],
            },
        )
        monkeypatch.setattr(douban, "_rexxar_search_blocked", True)
        foreign, rating = _fetch_douban_search("测试剧", 2023)
        assert foreign == "Test"
        assert rating == "7.0"

    def test_non_movie_types_filtered(self, monkeypatch):
        # book/music 等非影视条目过滤
        self._fake(
            monkeypatch,
            suggest_items=[
                {"id": "9", "title": "同名书", "sub_title": "", "year": "2020",
                 "type": "book", "episode": ""},
                self._suggest("8", "同名影视", "2021", "Same Name"),
            ],
            detail={
                "title": "同名影视", "original_title": "Same Name",
                "rating": {"count": 1, "value": 6.0},
                "directors": [], "actors": [], "aka": [],
            },
        )
        monkeypatch.setattr(douban, "_rexxar_search_blocked", True)
        foreign, rating = _fetch_douban_search("同名影视")
        assert foreign == "Same Name"
        assert rating == "6.0"


class TestHintNameEntrySelection:
    """同名条目的主演/导演名甄别（合唱团 The Choral 事件）。"""

    def _entries(self):
        # (标题, 评分, 年份, 条目ID, 块文本)
        return [
            ("陽光女子合唱團", "7.3", 2025, "37193250",
             "阳光女子合唱团 7.3 原名:陽光女子合唱團 / 林孝谦 / 陈意涵 / 2025"),
            ("The Choral", "6.7", 2025, "36828836",
             "合唱团 6.7 原名:The Choral / 尼古拉斯·希特纳 / 拉尔夫·费因斯 / 2025"),
        ]

    def test_hint_prefers_cast_matching_entry(self):
        from douban import _choose_entry
        name, rating, sid = _choose_entry(
            self._entries(), "合唱团", 2025, ["拉尔夫·费因斯"]
        )
        assert name == "The Choral"
        assert rating == "6.7"
        assert sid == "36828836"

    def test_no_hint_keeps_relevance_order(self):
        from douban import _choose_entry
        name, rating, _ = _choose_entry(self._entries(), "合唱团", 2025)
        assert name == "陽光女子合唱團"
        assert rating == "7.3"

    def test_hint_without_match_falls_back(self):
        from douban import _choose_entry
        name, _, _ = _choose_entry(
            self._entries(), "合唱团", 2025, ["汤姆·汉克斯"]
        )
        assert name == "陽光女子合唱團"

    def test_search_movie_threads_hints(self, monkeypatch):
        captured = {}

        def mock_fetch(name, year=None, hint_names=None):
            captured["hint_names"] = hint_names
            return ("Test Name", "7.0")

        monkeypatch.setattr(douban, "_fetch_douban_search", mock_fetch)
        douban._cache.clear()
        _, _ = search_movie("hint_thread_test", 2025, ["某主演"])
        assert captured["hint_names"] == ["某主演"]
