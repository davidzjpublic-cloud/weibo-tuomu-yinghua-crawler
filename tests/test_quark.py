# -*- coding: utf-8 -*-
"""
Quark 网盘模块单元测试
"""

from unittest.mock import MagicMock, patch

import pytest

from quark import (
    QuarkClient,
    enrich_comments,
    extract_quark_links,
    extract_quark_links_with_expansion,
    find_quark_link_in_comments,
    parse_share_file_name,
)


@pytest.fixture
def quark_client():
    return QuarkClient("dummy_cookie")


class TestQuarkLinkExtraction:

    def test_extract_direct_quark_link(self):
        text = "《肖申克的救赎》\nhttps://pan.quark.cn/s/abc123\n见平"
        links = extract_quark_links(text)
        assert links == ["https://pan.quark.cn/s/abc123"]

    def test_extract_sinaurl_encoded_quark_link(self):
        text = "《肖申克的救赎》\nhttps://weibo.cn/sinaurl?u=https%3A%2F%2Fpan.quark.cn%2Fs%2Fabc123\n见平"
        links = extract_quark_links(text)
        assert links == ["https://pan.quark.cn/s/abc123"]

    def test_extract_bare_quark_link(self):
        text = "《肖申克的救赎》\npan.quark.cn/s/abc123\n见平"
        links = extract_quark_links(text)
        assert links == ["https://pan.quark.cn/s/abc123"]

    def test_extract_quark_links_dedup(self):
        text = "https://pan.quark.cn/s/abc123 pan.quark.cn/s/abc123"
        links = extract_quark_links(text)
        assert links == ["https://pan.quark.cn/s/abc123"]

    def test_extract_quark_links_with_tcn_expansion(self):
        def fake_expander(url):
            if "t.cn" in url:
                return "https://pan.quark.cn/s/expanded456"
            return None

        text = "《肖申克的救赎》\nhttps://t.cn/xyz789\n见平"
        links = extract_quark_links_with_expansion(text, fake_expander)
        assert links == ["https://pan.quark.cn/s/expanded456"]


class TestEnrichComments:

    def test_enrich_url_struct_quark_link(self):
        comments = [
            {
                "url_struct": [
                    {"short_url": "", "long_url": "https://pan.quark.cn/s/abc123"},
                ],
            }
        ]
        enrich_comments(comments)
        assert comments[0]["_quark_link"] == "https://pan.quark.cn/s/abc123"

    def test_enrich_url_struct_short_link(self):
        comments = [
            {
                "url_struct": [
                    {"short_url": "https://t.cn/xyz", "long_url": ""},
                ],
            }
        ]
        enrich_comments(comments)
        assert comments[0].get("_short_link") == "https://t.cn/xyz"
        assert "_quark_link" not in comments[0]

    def test_enrich_topic_struct_quark_link(self):
        comments = [
            {
                "topic_struct": [
                    {"topic_url": "https://pan.quark.cn/s/abc123"},
                ],
            }
        ]
        enrich_comments(comments)
        assert comments[0]["_quark_link"] == "https://pan.quark.cn/s/abc123"


class TestFindQuarkLinkInComments:

    def test_find_structured_quark_link(self):
        comments = [
            {"_quark_link": "https://pan.quark.cn/s/abc123"},
        ]
        link = find_quark_link_in_comments(comments, lambda x: None)
        assert link == "https://pan.quark.cn/s/abc123"

    def test_find_link_by_expanding_short_link(self):
        comments = [
            {"_short_link": "https://t.cn/xyz"},
        ]

        def fake_expander(url):
            return "https://pan.quark.cn/s/expanded456"

        link = find_quark_link_in_comments(comments, fake_expander)
        assert link == "https://pan.quark.cn/s/expanded456"

    def test_find_link_from_comment_text(self):
        comments = [
            {"text": "见平👇 https://pan.quark.cn/s/abc123"},
        ]
        link = find_quark_link_in_comments(comments, lambda x: None)
        assert link == "https://pan.quark.cn/s/abc123"

    def test_find_no_link(self):
        comments = [{"text": "谢谢分享"}]
        link = find_quark_link_in_comments(comments, lambda x: None)
        assert link is None


class TestParseShareFileName:

    def test_parse_name_and_year(self):
        result = parse_share_file_name("贝尔法斯特天堂路2026")
        assert result["chinese_name"] == "贝尔法斯特天堂路"
        assert result["year"] == 2026
        assert result["douban_rating"] is None

    def test_parse_name_year_and_rating(self):
        result = parse_share_file_name("盗梦空间2010豆瓣9.3.mkv")
        assert result["chinese_name"] == "盗梦空间"
        assert result["year"] == 2010
        assert result["douban_rating"] == "豆瓣9.3"

    def test_parse_name_with_spaces_and_rating(self):
        result = parse_share_file_name("盗梦空间 2010 豆瓣 9.3.mp4")
        assert result["chinese_name"] == "盗梦空间"
        assert result["year"] == 2010
        assert result["douban_rating"] == "豆瓣9.3"

    def test_parse_name_without_year(self):
        result = parse_share_file_name("肖申克的救赎 1080p.mp4")
        assert result["chinese_name"] == "肖申克的救赎"
        assert result["year"] is None
        assert result["douban_rating"] is None

    def test_parse_name_only_rating(self):
        result = parse_share_file_name("霸王别姬 豆瓣9.6.mkv")
        assert result["chinese_name"] == "霸王别姬"
        assert result["year"] is None
        assert result["douban_rating"] == "豆瓣9.6"

    def test_parse_db_rating(self):
        result = parse_share_file_name("寄生虫2019db8.7.mp4")
        assert result["chinese_name"] == "寄生虫"
        assert result["year"] == 2019
        assert result["douban_rating"] == "豆瓣8.7"

    def test_parse_year_in_middle(self):
        result = parse_share_file_name("2012世界末日2009")
        assert result["chinese_name"] == "2012世界末日"
        assert result["year"] == 2009

    def test_parse_name_with_year_in_parentheses(self):
        result = parse_share_file_name("《拣选》剧组与贝尔·格里尔斯一起荒野求生 (2026)")
        assert result["chinese_name"] == "《拣选》剧组与贝尔·格里尔斯一起荒野求生"
        assert result["year"] == 2026
        assert result["douban_rating"] is None

    def test_parse_name_with_year_in_fullwidth_parentheses(self):
        result = parse_share_file_name("某片（2020）")
        assert result["chinese_name"] == "某片"
        assert result["year"] == 2020

    def test_parse_empty_parentheses_at_end(self):
        result = parse_share_file_name("测试片 ()")
        assert result["chinese_name"] == "测试片"
        assert result["year"] is None
        assert result["douban_rating"] is None


class TestQuarkClient:

    def test_get_pwd_id(self, quark_client):
        assert quark_client._get_pwd_id("https://pan.quark.cn/s/abc123") == "abc123"
        assert quark_client._get_pwd_id("invalid") is None

    def test_list_share_files_success(self, quark_client):
        # Mock _request to return token then detail
        responses = [
            {
                "code": 0,
                "data": {"stoken": "token123"},
            },
            {
                "code": 0,
                "data": {
                    "list": [
                        {"fid": "1", "file_name": "贝尔法斯特天堂路2026"},
                    ],
                },
            },
        ]
        quark_client._request = MagicMock(side_effect=responses)

        files = quark_client.list_share_files("https://pan.quark.cn/s/abc123")
        assert len(files) == 1
        assert files[0]["file_name"] == "贝尔法斯特天堂路2026"

    def test_list_share_files_token_failure(self, quark_client):
        quark_client._request = MagicMock(return_value={"code": 40001, "message": "fail"})
        files = quark_client.list_share_files("https://pan.quark.cn/s/abc123")
        assert files == []

    def test_get_first_file_name(self, quark_client):
        quark_client.list_share_files = MagicMock(
            return_value=[{"file_name": "贝尔法斯特天堂路2026"}]
        )
        name = quark_client.get_first_file_name("https://pan.quark.cn/s/abc123")
        assert name == "贝尔法斯特天堂路2026"

    def test_find_or_create_dir_existing(self, quark_client):
        quark_client.list_my_files = MagicMock(
            return_value=[
                {"fid": "dir1", "file_name": "来自：分享", "file_type": 0},
            ]
        )
        quark_client._drive_request = MagicMock(
            return_value={"code": 0, "data": {"fid": "dir2"}}
        )
        fid = quark_client.find_or_create_dir("来自：分享/【拓临】")
        assert fid == "dir2"

    def test_save_share_files_success(self, quark_client):
        quark_client._get_share_info = MagicMock(
            return_value={"data": {"stoken": "token123"}}
        )
        quark_client._request = MagicMock(
            return_value={
                "code": 0,
                "data": {
                    "list": [{"fid": "fid1", "share_fid_token": "tok1"}],
                },
            }
        )
        quark_client._drive_request = MagicMock(
            return_value={
                "code": 0,
                "data": {
                    "task_id": "task1",
                    "task_sync": True,
                    "task_resp": {
                        "code": 0,
                        "data": {
                            "save_as": {
                                "save_as_top_fids": ["saved1"],
                            },
                        },
                    },
                },
            }
        )
        saved = quark_client.save_share_files(
            "https://pan.quark.cn/s/abc123",
            [{"fid": "fid1", "share_fid_token": "tok1"}],
            "target_dir_fid",
        )
        assert len(saved) == 1
        assert saved[0]["fid"] == "saved1"
        assert saved[0]["original_fid"] == "fid1"

    def test_rename_file_success(self, quark_client):
        quark_client._drive_request = MagicMock(
            return_value={"code": 0, "data": {}}
        )
        assert quark_client.rename_file("fid1", "new name") is True

    def test_rename_file_failure(self, quark_client):
        quark_client._drive_request = MagicMock(
            return_value={"code": 40001, "message": "fail"}
        )
        assert quark_client.rename_file("fid1", "new name") is False

    def test_save_and_rename(self, quark_client):
        quark_client.find_or_create_dir = MagicMock(return_value="target_fid")
        quark_client.save_share_files = MagicMock(
            return_value=[{"fid": "saved1", "original_fid": "fid1", "file_name": "orig"}]
        )
        quark_client.rename_file = MagicMock(return_value=True)

        items = [{"fid": "fid1", "file_name": "orig", "final_name": "final"}]
        results = quark_client.save_and_rename(
            "https://pan.quark.cn/s/abc123",
            items,
            "来自：分享/【拓临】",
            lambda item: item.get("final_name"),
        )
        assert len(results) == 1
        assert results[0].get("renamed") is True
        assert results[0].get("new_name") == "final"

    def test_get_first_file_name_fallback_to_title(self, quark_client):
        quark_client.list_share_files = MagicMock(return_value=[])
        quark_client.get_share_title = MagicMock(return_value="FallbackTitle2025")
        name = quark_client.get_first_file_name("https://pan.quark.cn/s/abc123")
        assert name == "FallbackTitle2025"

    def test_client_without_cookie(self):
        client = QuarkClient("")
        files = client.list_share_files("https://pan.quark.cn/s/abc123")
        assert files == []

    @patch("quark.requests.Session")
    def test_request_uses_cookie(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        QuarkClient("test_cookie")

        # 验证构造时给 session 设置了 Cookie
        update_call = None
        for call in mock_session.headers.update.call_args_list:
            args = call[0]
            if args and isinstance(args[0], dict) and args[0].get("Cookie") == "test_cookie":
                update_call = call
                break
        assert update_call is not None, "session.headers.update 未使用传入的 cookie"

    def test_rename_file_replaces_halfwidth_slash(self, quark_client):
        # 回归：夸克不接受文件名中的半角“/”，重命名前替换为全角“／”（19/20 成年初体验）
        captured = {}

        def fake_drive_request(method, url, **kwargs):
            captured.update(kwargs.get("json") or {})
            return {"code": 0}

        quark_client._drive_request = MagicMock(side_effect=fake_drive_request)
        ok = quark_client.rename_file("fid123", "19/20 成年初体验 2023 （冷门高分综艺 全13期 韩语中字 豆瓣7.6）")
        assert ok is True
        assert captured.get("file_name") == "19／20 成年初体验 2023 （冷门高分综艺 全13期 韩语中字 豆瓣7.6）"
        assert "/" not in captured.get("file_name")

    def test_rename_file_keeps_name_without_slash(self, quark_client):
        captured = {}

        def fake_drive_request(method, url, **kwargs):
            captured.update(kwargs.get("json") or {})
            return {"code": 0}

        quark_client._drive_request = MagicMock(side_effect=fake_drive_request)
        ok = quark_client.rename_file("fid123", "男人 Men 2022 （恐怖片）")
        assert ok is True
        assert captured.get("file_name") == "男人 Men 2022 （恐怖片）"
