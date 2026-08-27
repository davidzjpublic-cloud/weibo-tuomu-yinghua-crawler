# -*- coding: utf-8 -*-
"""utils.py 单元测试"""

import pytest
from datetime import date

from utils import safe_filename, clean_html, get_publish_date, parse_publish_time


class TestSafeFilename:
    def test_none_returns_empty(self):
        assert safe_filename(None) == ""

    def test_empty_string(self):
        assert safe_filename("") == ""

    def test_normal_text_unchanged(self):
        assert safe_filename("杀人者的购物中心") == "杀人者的购物中心"

    def test_removes_illegal_chars(self):
        assert safe_filename('a<b>c"d|e?f*g') == "abcdefg"

    def test_preserves_slash(self):
        """片名如 '19/20' 自带的斜杠应保留。"""
        assert safe_filename("19/20") == "19/20"

    def test_colon_to_fullwidth(self):
        assert safe_filename("Title: Subtitle") == "Title：Subtitle"

    def test_strips_spaces_around_fullwidth_colon(self):
        assert safe_filename("Title： Subtitle") == "Title：Subtitle"
        assert safe_filename("Title ：Subtitle") == "Title：Subtitle"

    def test_strips_leading_trailing_spaces(self):
        assert safe_filename("  hello  ") == "hello"

    def test_backslash_removed(self):
        assert safe_filename("path\\file") == "pathfile"


class TestCleanHtml:
    def test_none_returns_empty(self):
        assert clean_html(None) == ""

    def test_empty_string(self):
        assert clean_html("") == ""

    def test_plain_text_unchanged(self):
        assert clean_html("hello world") == "hello world"

    def test_br_to_newline(self):
        assert clean_html("line1<br/>line2") == "line1\nline2"
        assert clean_html("line1<br>line2") == "line1\nline2"
        assert clean_html("line1<br />line2") == "line1\nline2"

    def test_removes_tags(self):
        assert clean_html("<p>hello</p>") == "hello"
        assert clean_html('<a href="url">link</a>') == "link"

    def test_nested_tags(self):
        assert clean_html("<div><span>text</span></div>") == "text"

    def test_mixed_br_and_tags(self):
        assert clean_html("<p>line1<br/>line2</p>") == "line1\nline2"


class TestGetPublishDate:
    def test_none_returns_none(self):
        assert get_publish_date(None) is None

    def test_unix_timestamp(self):
        # 2026-08-15 00:00:00 UTC approximately
        result = get_publish_date(1786742400)
        assert result is not None
        assert result.year == 2026

    def test_date_string_yyyy_mm_dd(self):
        assert get_publish_date("2026-08-15") == date(2026, 8, 15)

    def test_datetime_string(self):
        result = get_publish_date("2026-08-15 14:30:00")
        assert result == date(2026, 8, 15)

    def test_empty_string_returns_none(self):
        assert get_publish_date("") is None

    def test_invalid_string_returns_none(self):
        assert get_publish_date("not a date") is None


class TestParsePublishTime:
    def test_matching_date(self):
        assert parse_publish_time("2026-08-15", "2026-08-15") is True

    def test_non_matching_date(self):
        assert parse_publish_time("2026-08-15", "2026-08-16") is False

    def test_none_returns_false(self):
        assert parse_publish_time(None, "2026-08-15") is False

    def test_invalid_returns_false(self):
        assert parse_publish_time("not a date", "2026-08-15") is False

    def test_yesterday_keyword(self):
        """'昨天' 字符串应匹配昨天的日期。"""
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert parse_publish_time("昨天", yesterday) is True
