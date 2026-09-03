# -*- coding: utf-8 -*-
"""完成一条微博后在 CLI 回显完整文件名的单元测试。"""

from unittest.mock import MagicMock

import main as main_module
from main import Lobster
from models import MovieInfo


SHARE_LINK = "https://pan.quark.cn/s/abc123"


def make_lobster(tmp_path, save_enabled=False):
    crawler = MagicMock()
    lobster = Lobster(
        crawler=crawler,
        max_pages=1,
        target_date="2026-08-31",
        output_json=str(tmp_path / "results_2026-08-31.json"),
        output_txt=str(tmp_path / "filenames_2026-08-31.txt"),
        processed_file=str(tmp_path / "processed.json"),
        save_enabled=save_enabled,
    )
    # 提取器与正文链接走真实逻辑太重，直接替换为固定结果
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


class TestFilenameEcho:

    def test_echo_after_weibo_without_save(self, tmp_path, monkeypatch, capsys):
        """不带 --save：完成微博后在控制台回显完整文件名。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(tmp_path)
        crawler.quark_client.list_share_files.return_value = [
            {"fid": "f1", "file_name": "测试电影 2020"}
        ]

        results = lobster.process_weibo(make_weibo())

        assert len(results) == 1
        out = capsys.readouterr().out
        assert f"文件名: {results[0].generate_filename()}" in out

    def test_no_echo_when_transfer_already_printed(self, tmp_path, monkeypatch, capsys):
        """带 --save 且转存成功：「转存 n. …」已回显过同名，不再重复。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(tmp_path, save_enabled=True)
        lobster._save_to_quark = MagicMock(return_value=True)
        crawler.quark_client.list_share_files.return_value = [
            {"fid": "f1", "file_name": "测试电影 2020"}
        ]

        results = lobster.process_weibo(make_weibo())

        lobster._save_to_quark.assert_called_once()
        assert results[0].saved is True
        assert "文件名:" not in capsys.readouterr().out

    def test_echo_each_file_of_multi_file_weibo(self, tmp_path, monkeypatch, capsys):
        """一个微博多个夸克文件：每个结果各回显一行。"""
        patch_helpers(monkeypatch)
        lobster, crawler = make_lobster(tmp_path)
        crawler.quark_client.list_share_files.return_value = [
            {"fid": "f1", "file_name": "测试电影 2020"},
            {"fid": "f2", "file_name": "测试电影：续集 2022"},
        ]

        results = lobster.process_weibo(make_weibo())

        assert len(results) == 2
        out = capsys.readouterr().out
        for r in results:
            assert f"文件名: {r.generate_filename()}" in out
