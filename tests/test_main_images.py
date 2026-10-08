# -*- coding: utf-8 -*-
"""微博配图失败持久化与跨运行补传的单元测试。"""

import json
from unittest.mock import MagicMock

import main as main_module
from main import Lobster


def make_lobster(tmp_path):
    crawler = MagicMock()
    return Lobster(
        crawler=crawler,
        max_pages=1,
        target_date="2026-08-31",
        output_json=str(tmp_path / "results_2026-08-31.json"),
        output_txt=str(tmp_path / "filenames_2026-08-31.txt"),
        saved_file=str(tmp_path / "saved.json"),
    ), crawler


FOLDER_NAME = "咒怨：诅咒之家 呪怨：呪いの家 2020 （三宅唱导演 恐怖剧集 全6集 日语中字 豆瓣6.7）"


def write_entries(lobster, entries):
    lobster._save_failed_images(entries)


class TestFailedImagesPersistence:

    def test_record_failed_image_dedup(self, tmp_path):
        lobster, _ = make_lobster(tmp_path)
        entry = {
            "image_url": "https://wx3.sinaimg.cn/large/abc.jpg",
            "image_name": "5337578643394114_img_1.jpg",
            "save_dir": "来自：分享/【拓临】",
            "folder_name": FOLDER_NAME,
        }
        lobster._record_failed_image(entry)
        lobster._record_failed_image(dict(entry))
        entries = lobster._load_failed_images()
        assert len(entries) == 1
        assert entries[0]["image_name"] == "5337578643394114_img_1.jpg"

    def test_load_missing_file_returns_empty(self, tmp_path):
        lobster, _ = make_lobster(tmp_path)
        assert lobster._load_failed_images() == []


class TestRetryFailedImages:

    def test_retry_success_clears_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main_module.time, "sleep", lambda s: None)
        lobster, crawler = make_lobster(tmp_path)
        write_entries(lobster, [{
            "image_url": "https://wx3.sinaimg.cn/large/abc.jpg",
            "image_name": "5337578643394114_img_1.jpg",
            "save_dir": "来自：分享/【拓临】",
            "folder_name": FOLDER_NAME,
        }])
        client = crawler.quark_client
        client.find_or_create_dir.return_value = "root_fid"
        # 第一次列目录：按目录名定位子文件夹；第二次：检查图片是否已存在
        client.list_all_my_files.side_effect = [
            [{"fid": "folder_fid", "file_name": FOLDER_NAME, "file_type": 0}],
            [],
        ]
        lobster._upload_image_with_retry = MagicMock(return_value="new_img_fid")

        lobster._retry_failed_images()

        lobster._upload_image_with_retry.assert_called_once_with(
            "https://wx3.sinaimg.cn/large/abc.jpg",
            "5337578643394114_img_1.jpg",
            "folder_fid",
        )
        assert lobster._load_failed_images() == []

    def test_retry_skips_when_image_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main_module.time, "sleep", lambda s: None)
        lobster, crawler = make_lobster(tmp_path)
        write_entries(lobster, [{
            "image_url": "https://wx3.sinaimg.cn/large/abc.jpg",
            "image_name": "5337578643394114_img_1.jpg",
            "save_dir": "来自：分享/【拓临】",
            "folder_name": FOLDER_NAME,
        }])
        client = crawler.quark_client
        client.find_or_create_dir.return_value = "root_fid"
        client.list_all_my_files.side_effect = [
            [{"fid": "folder_fid", "file_name": FOLDER_NAME, "file_type": 0}],
            [{"fid": "img_fid", "file_name": "5337578643394114_img_1.jpg"}],
        ]
        lobster._upload_image_with_retry = MagicMock()

        lobster._retry_failed_images()

        lobster._upload_image_with_retry.assert_not_called()
        assert lobster._load_failed_images() == []

    def test_retry_failure_keeps_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main_module.time, "sleep", lambda s: None)
        lobster, crawler = make_lobster(tmp_path)
        write_entries(lobster, [{
            "image_url": "https://wx3.sinaimg.cn/large/abc.jpg",
            "image_name": "5337578643394114_img_1.jpg",
            "save_dir": "来自：分享/【拓临】",
            "folder_name": FOLDER_NAME,
        }])
        client = crawler.quark_client
        client.find_or_create_dir.return_value = "root_fid"
        client.list_all_my_files.side_effect = [
            [{"fid": "folder_fid", "file_name": FOLDER_NAME, "file_type": 0}],
            [],
        ]
        lobster._upload_image_with_retry = MagicMock(return_value=None)

        lobster._retry_failed_images()

        assert len(lobster._load_failed_images()) == 1

    def test_retry_folder_missing_keeps_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main_module.time, "sleep", lambda s: None)
        lobster, crawler = make_lobster(tmp_path)
        write_entries(lobster, [{
            "image_url": "https://wx3.sinaimg.cn/large/abc.jpg",
            "image_name": "5337578643394114_img_1.jpg",
            "save_dir": "来自：分享/【拓临】",
            "folder_name": FOLDER_NAME,
        }])
        client = crawler.quark_client
        client.find_or_create_dir.return_value = "root_fid"
        client.list_all_my_files.return_value = []  # 目录被移动，找不到子文件夹
        lobster._upload_image_with_retry = MagicMock()

        lobster._retry_failed_images()

        lobster._upload_image_with_retry.assert_not_called()
        assert len(lobster._load_failed_images()) == 1


class TestSaveToQuarkImageTarget:
    """微博配图目标文件夹定位：最终名含半角“/”时，落盘名是全角“／”变体。"""

    def test_poster_goes_into_fullwidth_slash_folder(self, tmp_path):
        lobster, crawler = make_lobster(tmp_path)
        final_name = (
            "911：总统作战室 9/11：Inside the President’s War Room 2021 "
            "（高分纪录片 英语中字 豆瓣8.1）"
        )
        movie = MagicMock()
        movie.quark_fid = "share_fid"
        movie.chinese_name = "911：总统作战室"
        movie.quark_file_name = "911总统作战室2021"
        movie.generate_filename.return_value = final_name

        client = crawler.quark_client
        client.find_or_create_dir.return_value = "root_fid"
        # 夸克落盘名把半角“/”换成全角“／”，定位子文件夹时须同时匹配
        disk_name = final_name.replace("/", "／")
        client.list_all_my_files.side_effect = [
            [],  # 冲突检查：无同名项
            [{"fid": "folder_fid", "file_name": disk_name, "file_type": 0}],
        ]
        client.save_and_rename.return_value = [{"renamed": True}]
        lobster._upload_image_with_retry = MagicMock(return_value="img_fid")

        ok = lobster._save_to_quark(
            "https://pan.quark.cn/s/abc",
            [movie],
            "5341934461913089",
            ["https://wx3.sinaimg.cn/large/abc.jpg"],
        )

        assert ok is True
        # 配图应上传到全角“／”名的子文件夹，而不是根目录 root_fid
        lobster._upload_image_with_retry.assert_called_once_with(
            "https://wx3.sinaimg.cn/large/abc.jpg",
            "5341934461913089_img_1.jpg",
            "folder_fid",
        )

    def test_poster_queued_when_listing_fails(self, tmp_path):
        # 列目录定位子文件夹失败（网络重试耗尽）时，配图不得误传根目录，
        # 应转入待补传队列并记录 folder_name 供重定位（会见波尔布特，2026-10-08）
        lobster, crawler = make_lobster(tmp_path)
        final_name = (
            "会见波尔布特 Rendez-vous avec Pol Pot 2024 "
            "（潘礼德导演 亚洲电影大奖最佳导演提名作品 历史片 豆瓣7.2）"
        )
        movie = MagicMock()
        movie.quark_fid = "share_fid"
        movie.chinese_name = "会见波尔布特"
        movie.quark_file_name = "会见波尔布特2024"
        movie.generate_filename.return_value = final_name

        client = crawler.quark_client
        client.find_or_create_dir.return_value = "root_fid"
        client.list_all_my_files.side_effect = [
            [],  # 冲突检查：无同名项
            RuntimeError("列出目录失败 (pdir_fid=root_fid, page=1): None"),
        ]
        client.save_and_rename.return_value = [{"renamed": True}]
        lobster._upload_image_with_retry = MagicMock()

        ok = lobster._save_to_quark(
            "https://pan.quark.cn/s/abc",
            [movie],
            "5351456907725616",
            ["https://wx2.sinaimg.cn/large/abc.jpg"],
        )

        assert ok is True  # 转存本身成功，配图是附属品
        lobster._upload_image_with_retry.assert_not_called()  # 不误传到根目录
        entries = lobster._load_failed_images()
        assert len(entries) == 1
        assert entries[0]["image_name"] == "5351456907725616_img_1.jpg"
        assert entries[0]["folder_name"] == final_name


class TestUploadImageWithRetry:

    def test_success_returns_fid(self, tmp_path):
        lobster, crawler = make_lobster(tmp_path)
        resp = MagicMock()
        resp.content = b"image-bytes"
        crawler.session.get.return_value = resp
        crawler.quark_client.upload_file.return_value = "fid1"

        fid = lobster._upload_image_with_retry(
            "https://wx3.sinaimg.cn/large/abc.jpg", "img.jpg", "target_fid"
        )

        assert fid == "fid1"
        crawler.quark_client.upload_file.assert_called_once_with(
            b"image-bytes", "img.jpg", "target_fid"
        )

    def test_all_failures_return_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main_module.time, "sleep", lambda s: None)
        lobster, crawler = make_lobster(tmp_path)
        crawler.session.get.side_effect = ConnectionError("proxy down")

        fid = lobster._upload_image_with_retry(
            "https://wx3.sinaimg.cn/large/abc.jpg", "img.jpg", "target_fid"
        )

        assert fid is None
        assert crawler.session.get.call_count == 3

    def test_none_fid_counts_as_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main_module.time, "sleep", lambda s: None)
        lobster, crawler = make_lobster(tmp_path)
        resp = MagicMock()
        resp.content = b"image-bytes"
        crawler.session.get.return_value = resp
        crawler.quark_client.upload_file.return_value = None

        fid = lobster._upload_image_with_retry(
            "https://wx3.sinaimg.cn/large/abc.jpg", "img.jpg", "target_fid"
        )

        assert fid is None
        # 未返回 fid 视为失败并重试，共 3 次
        assert crawler.quark_client.upload_file.call_count == 3
