# -*- coding: utf-8 -*-
"""saved_weibo.json 标记语义的单元测试。

2026-10-08 起：标记与 --skip-saved 解耦——只要带 --save 运行且
转存成功就写入标记；--skip-saved 只负责跳过已标记微博；
不带 --save 的验证运行永不标记（否则会把待转存项跳过）。
"""

from unittest.mock import MagicMock

import main as main_module
from main import Lobster
from models import MovieInfo


SHARE_LINK = "https://pan.quark.cn/s/abc123"


def make_lobster(tmp_path, save_enabled=False, skip_saved=False):
    crawler = MagicMock()
    lobster = Lobster(
        crawler=crawler,
        max_pages=1,
        target_date="2026-08-31",
        output_json=str(tmp_path / "results_2026-08-31.json"),
        output_txt=str(tmp_path / "filenames_2026-08-31.txt"),
        saved_file=str(tmp_path / "saved.json"),
        skip_saved=skip_saved,
        save_enabled=save_enabled,
    )
    lobster.extractor = MagicMock()
    lobster.extractor.extract.return_value = MovieInfo(
        chinese_name="测试电影",
        year="2020",
        raw_text="《测试电影》2020",
    )
    return lobster, crawler


def patch_helpers(monkeypatch):
    monkeypatch.setattr(
        main_module, "extract_quark_links_with_expansion", lambda text, exp: [SHARE_LINK]
    )
    monkeypatch.setattr(main_module, "search_movie", lambda *a, **k: (None, None))


def make_weibo():
    return {
        "id": "5337578643394114",
        "text": "《测试电影》2020 夸克链接",
        "created_at": "2026-08-31 12:00:00",
    }


class TestSavedMarker:

    def test_save_success_marks_without_skip_flag(self, tmp_path, monkeypatch):
        """带 --save 转存成功：即使不带 --skip-saved 也写入标记。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(tmp_path, save_enabled=True)
        lobster._save_to_quark = MagicMock(return_value=True)
        crawler.quark_client.list_share_files.return_value = [
            {"fid": "f1", "file_name": "测试电影 2020"}
        ]

        lobster.process_weibo(make_weibo())

        crawler.add_saved_id.assert_called_once_with("5337578643394114")
        crawler.save_saved_ids.assert_called_once_with(lobster.saved_file)

    def test_save_failure_not_marked(self, tmp_path, monkeypatch):
        """带 --save 但转存失败：不标记，保留待下次重试。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(tmp_path, save_enabled=True)
        lobster._save_to_quark = MagicMock(return_value=False)
        crawler.quark_client.list_share_files.return_value = [
            {"fid": "f1", "file_name": "测试电影 2020"}
        ]

        lobster.process_weibo(make_weibo())

        crawler.add_saved_id.assert_not_called()
        crawler.save_saved_ids.assert_not_called()

    def test_dry_run_never_marks(self, tmp_path, monkeypatch):
        """不带 --save 的验证运行：即便带 --skip-saved 也不标记。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(
            tmp_path, save_enabled=False, skip_saved=True
        )
        crawler.quark_client.list_share_files.return_value = [
            {"fid": "f1", "file_name": "测试电影 2020"}
        ]

        lobster.process_weibo(make_weibo())

        crawler.add_saved_id.assert_not_called()
        crawler.save_saved_ids.assert_not_called()

    def test_skip_flag_skips_marked_weibo(self, tmp_path, monkeypatch):
        """--skip-saved 只负责跳过：已标记微博不再处理。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(tmp_path, skip_saved=True)
        crawler.saved_ids = {"5337578643394114"}

        results = lobster.process_weibo(make_weibo())

        assert results == []
        crawler.quark_client.list_share_files.assert_not_called()
