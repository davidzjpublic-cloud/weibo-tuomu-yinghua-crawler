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
    """隔离豆瓣磁盘缓存：测试写入临时文件，避免污染真实 .douban_cache.json。"""
    monkeypatch.setattr(douban, "CACHE_FILE", tmp_path / "douban_cache_test.json")
    douban._cache.clear()
    yield
    douban._cache.clear()


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
    def _fake_session(monkeypatch, search_title, aka_list, sid="30394484"):
        """构造搜索页 + rexxar API 响应，返回 rexxar 请求计数。"""
        rexxar_calls = [0]

        class FakeResp:
            def __init__(self, text, status_code=200):
                self.text = text
                self.status_code = status_code

            def json(self):
                import json as _json
                return _json.loads(self.text)

        search_html = (
            '<div class="result">'
            f'<a class="nbg" href="https://www.douban.com/link2/" '
            f'onclick="moreurl(this,{{sid: {sid}}})" title="{search_title}">'
            '<img src="https://img.doubanio.com/x.jpg"></a>'
            '<span class="rating_nums">7.8</span>（15856人评价）2019</div>'
        )

        def fake_get(url, *args, **kwargs):
            if "douban.com/search" in url:
                return FakeResp(search_html)
            if "rexxar" in url:
                rexxar_calls[0] += 1
                import json as _json
                return FakeResp(_json.dumps({"title": "然后我们跳了舞", "aka": aka_list}))
            raise AssertionError(f"意外请求: {url}")

        monkeypatch.setattr(douban.requests, "get", fake_get)
        douban._last_request_time = 0.0
        return rexxar_calls

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
        calls = self._fake_session(
            monkeypatch, "လိပ်ပြာလင်္ကာ", ["灵魂乐"]
        )
        foreign, rating = _fetch_douban_search("魂歌")
        assert foreign == "လိပ်ပြာလင်္ကာ"
        assert calls[0] == 1

    def test_major_script_skips_rexxar(self, monkeypatch):
        calls = self._fake_session(monkeypatch, "슈룹", ["And Then We Danced"])
        foreign, rating = _fetch_douban_search("王后伞下")
        assert foreign == "슈룹"
        assert calls[0] == 0

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


class TestEntryYearParsing:
    """条目年份解析：评价人数（N人评）与超区间数字不应被当成上映年。

    回归案例：搜索“圣罗兰传”时，波尼洛版《Saint Laurent》块内
    “（2067人评）”被解析成 2067 年，导致 year=2014 过滤滑到错误条目。
    """

    @staticmethod
    def _search_html(blocks, unit="人评"):
        parts = []
        for title, rating, count, year_line in blocks:
            parts.append(
                '<div class="result">'
                f'<a class="nbg" href="https://movie.douban.com/subject/x" '
                f'title="{title}">'
                # 海报 URL 里的数字（p1197911950.jpg）不得被当成上映年
                f'<img src="https://img.doubanio.com/view/photo/'
                f'public/p1197911950.jpg">'
                f'<span class="rating_nums">{rating}</span>'
                f'（{count}{unit}） {year_line}'
                "</div>"
            )
        return "<html><body>" + "".join(parts) + "</body></html>"

    def test_rating_count_not_parsed_as_year(self, monkeypatch):
        class FakeResp:
            status_code = 200
            text = self._search_html(
                [
                    # 仅有未来年份（超区间）→ 年份应为 None，被 2014 过滤掉
                    ("Future Doc", "9.0", "300", "2067年上映"),
                    # “2067人评”不得当成 2067 年，真实年份取信息行的 2014
                    ("Saint Laurent", "7.2", "2067", "2014年上映"),
                    ("Yves Saint Laurent", "6.7", "12345", "2014年上映"),
                ]
            )

        monkeypatch.setattr(douban.requests, "get", lambda *a, **k: FakeResp())
        douban._last_request_time = 0.0
        foreign, rating = _fetch_douban_search("圣罗兰传", 2014)
        assert foreign == "Saint Laurent"
        assert rating == "7.2"

    def test_rating_count_with_jia_not_parsed_as_year(self, monkeypatch):
        """回归：搜索“水”时《Water》块内海报 URL “p1197911950.jpg”的
        1979/1950、评价人数“（1979人评价）”都被当年份，真实年份 2005
        匹配失败、错选同年份的《水果硬糖》(Hard Candy)。"""
        class FakeResp:
            status_code = 200
            text = self._search_html(
                [
                    ("Water", "8.4", "1979", "2005年上映"),
                    ("Hard Candy", "7.5", "9999", "2005年上映"),
                ],
                unit="人评价",
            )

        monkeypatch.setattr(douban.requests, "get", lambda *a, **k: FakeResp())
        douban._last_request_time = 0.0
        foreign, rating = _fetch_douban_search("水", 2005)
        assert foreign == "Water"
        assert rating == "8.4"


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
