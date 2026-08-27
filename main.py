# -*- coding: utf-8 -*-
"""
龙虾 - 拓木映画微博爬虫（模块化重构入口）

保留原始 lobster.py 不变，本文件作为新的命令行入口。
"""

import argparse
import html
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from config import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_LOG_FILE,
    DEFAULT_MAX_PAGES,
    DEFAULT_PROCESSED_FILE,
    DEFAULT_UID,
    OUTPUT_JSON_TEMPLATE,
    OUTPUT_TXT_TEMPLATE,
)
from crawler import WeiboCrawler
from douban import search_movie
from extractor import MovieExtractor
from models import MovieInfo
from quark import (
    extract_quark_links_with_expansion,
    find_quark_link_in_comments,
    parse_share_file_name,
)
from utils import clean_html, get_publish_date, parse_publish_time


# 项目根目录（即 main.py 所在目录），用于解析默认相对路径
PROJECT_ROOT = Path(__file__).resolve().parent


# 控制台上仍显示的 INFO 日志前缀（关键进度节点）；其余 INFO 只写入日志文件
CONSOLE_INFO_PREFIXES = (
    "=== ",
    "启动参数",
    "处理微博 [",
    "✅ 提取成功",
    "非影视内容",
    "开始转存",
    "转存完成",
    "结果已保存",
    "文件名列表已保存",
)


class ConsoleFilter(logging.Filter):
    """控制台精简过滤器：WARNING 及以上全放行，INFO 仅放行关键进度。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        return record.getMessage().startswith(CONSOLE_INFO_PREFIXES)


def setup_logging(verbose: bool = False) -> None:
    """配置日志输出到文件和控制台。

    文件日志始终记录完整 INFO 明细；控制台默认只显示关键进度与
    警告/错误，--verbose 时恢复完整输出（含 DEBUG 诊断信息）。
    """
    log_path = PROJECT_ROOT / DEFAULT_LOG_FILE
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    console_handler = logging.StreamHandler(sys.stdout)
    if verbose:
        root_level = logging.DEBUG
        file_handler.setLevel(logging.DEBUG)
    else:
        root_level = logging.INFO
        console_handler.addFilter(ConsoleFilter())
    logging.basicConfig(
        level=root_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[file_handler, console_handler],
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="龙虾 - 拓木映画微博爬虫（模块化版本）",
    )
    parser.add_argument(
        "--uid",
        default=DEFAULT_UID,
        help=f"目标微博用户 UID（默认: {DEFAULT_UID}）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"最大抓取页数（默认: {DEFAULT_MAX_PAGES}）",
    )
    parser.add_argument(
        "--target-date",
        default=None,
        help='目标日期，格式 "YYYY-MM-DD"（默认: 昨天）',
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / DEFAULT_CONFIG_FILE),
        help=f"Cookie 配置文件路径（默认: {PROJECT_ROOT / DEFAULT_CONFIG_FILE}）",
    )
    parser.add_argument(
        "--processed-file",
        default=str(PROJECT_ROOT / DEFAULT_PROCESSED_FILE),
        help=f"已处理微博 ID 记录文件（默认: {PROJECT_ROOT / DEFAULT_PROCESSED_FILE}）",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="JSON 结果输出路径（默认: output/results_目标日期.json）",
    )
    parser.add_argument(
        "--output-txt",
        default=None,
        help="文件名列表输出路径（默认: output/filenames_目标日期.txt）",
    )
    parser.add_argument(
        "--skip-processed",
        action="store_true",
        help="跳过已处理微博，并将新处理的微博写入 processed_weibo.json（默认不跳过、不写入）",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="启用夸克网盘转存与重命名（默认只输出文件名到 TXT/JSON）",
    )
    parser.add_argument(
        "--save-dir",
        default="来自：分享/【拓临】",
        help='夸克网盘转存目标目录（默认: "来自：分享/【拓临】"）',
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="控制台显示完整日志（含 DEBUG 诊断信息，默认只显示关键进度与警告）",
    )

    args = parser.parse_args()

    # 默认目标日期为昨天；显式传入时校验并归一化格式，保证文件名规范
    if not args.target_date:
        args.target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        try:
            args.target_date = datetime.strptime(
                args.target_date, "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
        except ValueError:
            parser.error(f'--target-date 格式应为 "YYYY-MM-DD": {args.target_date}')

    # 输出文件默认按目标日期命名（--target-date），而非运行当天
    if args.output_json is None:
        args.output_json = str(
            PROJECT_ROOT / OUTPUT_JSON_TEMPLATE.format(date=args.target_date)
        )
    if args.output_txt is None:
        args.output_txt = str(
            PROJECT_ROOT / OUTPUT_TXT_TEMPLATE.format(date=args.target_date)
        )

    # 若用户提供相对路径，也基于项目根目录解析
    args.config = str(PROJECT_ROOT / args.config)
    args.processed_file = str(PROJECT_ROOT / args.processed_file)
    if not os.path.isabs(args.output_json):
        args.output_json = str(PROJECT_ROOT / args.output_json)
    if not os.path.isabs(args.output_txt):
        args.output_txt = str(PROJECT_ROOT / args.output_txt)

    return args


class Lobster:
    """微博爬虫调度器。"""

    def __init__(
        self,
        crawler: WeiboCrawler,
        max_pages: int,
        target_date: str,
        output_json: str,
        output_txt: str,
        processed_file: str,
        skip_processed: bool = False,
        save_enabled: bool = False,
        save_dir: str = "来自：分享/【拓临】",
    ) -> None:
        self.crawler = crawler
        self.extractor = MovieExtractor()
        self.max_pages = max_pages
        self.target_date = target_date
        self.output_json = output_json
        self.output_txt = output_txt
        self.processed_file = processed_file
        self.skip_processed = skip_processed
        self.save_enabled = save_enabled
        self.save_dir = save_dir
        self.results: List[MovieInfo] = []
        self.seen_weibo_ids: set = set()

        # 加载已处理 ID（未启用 --skip-processed 时仅用于展示，不用于跳过）
        self.crawler.load_processed_ids(processed_file)
        if self.skip_processed:
            logging.info("已启用 --skip-processed：跳过已处理微博")
        else:
            logging.info("未启用 --skip-processed：不跳过已处理微博")

    def process_weibo(self, weibo: Dict) -> List[MovieInfo]:
        """处理单条微博，返回该微博下所有夸克文件对应的结果列表。"""
        weibo_id = str(weibo.get("id", weibo.get("mid", "")))

        if not weibo_id:
            logging.debug("微博 ID 为空，跳过")
            return []

        if self.skip_processed and weibo_id in self.crawler.processed_ids:
            logging.debug(f"跳过已处理微博: {weibo_id}")
            return []

        if weibo_id in self.seen_weibo_ids:
            logging.debug(f"跳过本运行内重复微博: {weibo_id}")
            return []
        self.seen_weibo_ids.add(weibo_id)

        text = weibo.get("text", "")
        text = clean_html(text)

        publish_time = weibo.get("created_at", weibo.get("timestamp", ""))

        # 1) 日期过滤：非目标日期直接跳过
        if not parse_publish_time(publish_time, self.target_date):
            logging.debug(f"非目标日期发布: {publish_time}")
            return []

        base_info = self.extractor.extract(text, weibo_id, str(publish_time))
        if base_info is None:
            logging.debug("跳过非影视内容")
            return []

        # 每处理一个影视微博前空一行，方便日志区分
        logging.info("")
        logging.info(f"处理微博 [{weibo_id}]: {text[:50]}...")

        # 提取微博图片（保存时一并上传到夸克目标目录）
        image_urls = self.crawler.extract_image_urls(weibo)
        if image_urls:
            logging.debug(f"  发现 {len(image_urls)} 张图片，保存时一并上传")

        # 1. 优先从正文找链接
        source_link = None
        text_links = extract_quark_links_with_expansion(text, self.crawler.expand_short_link)
        if text_links:
            source_link = text_links[0]
            logging.info(f"从正文找到夸克链接: {source_link}")

        # 2. 正文没有则到评论中找
        if not source_link:
            logging.debug("获取评论...")
            comments = self.crawler.get_comments(weibo_id)

            for i, comment in enumerate(comments[:3]):
                comment_text = clean_html(comment.get("text", ""))
                quark_from_struct = comment.get("_quark_link", "")
                short_link = comment.get("_short_link", "")
                logging.debug(
                    f"  评论 {i}: {comment_text[:50]}... "
                    f"结构化链接: {quark_from_struct[:40] if quark_from_struct else '无'} "
                    f"短链: {short_link[:30] if short_link else '无'}"
                )

            source_link = find_quark_link_in_comments(
                comments, self.crawler.expand_short_link
            )
            if source_link:
                logging.info(f"从评论找到夸克链接: {source_link}")
            else:
                logging.debug("  未找到夸克链接")

        if not source_link:
            return []

        # 3. 获取夸克分享中的所有文件/文件夹
        files = self.crawler.quark_client.list_share_files(source_link)
        if not files:
            title = self.crawler.quark_client.get_share_title(source_link)
            if title:
                files = [{"fid": None, "file_name": title}]
                logging.debug(f"分享无文件列表，使用分享标题: {title}")
            else:
                logging.debug("  未能获取夸克分享文件")
                return []

        results = []
        for item in files:
            file_name = item.get("file_name", "")
            parsed = parse_share_file_name(file_name)

            chinese_name = base_info.chinese_name or parsed.get("chinese_name")
            # 年份优先用夸克文件名末尾的（如“铁道人1984博帕尔事件2023”→2023，
            # 避免把片名中的“1984”误当年份）；文件名没有再用微博正文的
            year = parsed.get("year") or base_info.year
            file_douban_rating = parsed.get("douban_rating")

            # 用解析出的中文名搜索豆瓣外文名和评分（年份用于歧义中文名筛选）
            foreign_name = None
            douban_rating_from_search = None
            if chinese_name:
                foreign_name, douban_rating_from_search = search_movie(
                    chinese_name, year
                )

            douban_rating = file_douban_rating or douban_rating_from_search
            # 豆瓣搜索返回的纯数字评分统一归一化为“豆瓣X.X”（补 .0、截断多余小数）
            if douban_rating:
                rating_match = re.match(
                    r'^(\d+(?:\.\d+)?)$', str(douban_rating).strip()
                )
                if rating_match:
                    douban_rating = f"豆瓣{float(rating_match.group(1)):.1f}"

            info = MovieInfo(
                chinese_name=chinese_name,
                foreign_name=foreign_name,
                year=year,
                director=base_info.director,
                supervisor=base_info.supervisor,
                writer=base_info.writer,
                cast=base_info.cast,
                language=base_info.language,
                subtitle=base_info.subtitle,
                genre=base_info.genre,
                category=base_info.category,
                related_tag=base_info.related_tag,
                producer_tag=base_info.producer_tag,
                work_credit=base_info.work_credit,
                version_credit=base_info.version_credit,
                rating=base_info.rating,
                awards=base_info.awards,
                season=base_info.season,
                season_raw=base_info.season_raw,
                season_extra=base_info.season_extra,
                episodes=base_info.episodes,
                source_link=source_link,
                quark_fid=item.get("fid"),
                quark_file_name=item.get("file_name"),
                weibo_id=weibo_id,
                publish_time=str(publish_time),
                raw_text=base_info.raw_text,
                director_pos=base_info.director_pos,
                supervisor_pos=base_info.supervisor_pos,
                writer_pos=base_info.writer_pos,
                cast_pos=base_info.cast_pos,
            )
            info.douban_rating = douban_rating

            results.append(info)
            logging.info(f"  生成结果: {info.generate_filename()}")

        # 4. 转存（仅在 --save 时执行）
        saved_any = False
        if self.save_enabled and results:
            saved_any = self._save_to_quark(source_link, results, weibo_id, image_urls)
            # 逐条记录转存情况：有夸克 fid 且整单转存成功才算已转存
            for r in results:
                r.saved = saved_any and bool(r.quark_fid)

        # 仅当找到夸克链接时才标记为已处理并保存（调试模式下不写入）
        # 如果启用了转存但未实际转存成功，则保留到下次重试
        if self.save_enabled and not saved_any:
            logging.warning(f"微博 {weibo_id} 本次未成功转存，暂不标记为已处理")
        else:
            self.crawler.add_processed_id(weibo_id)
            if self.skip_processed:
                self.crawler.save_processed_ids(self.processed_file)
            else:
                logging.debug("未启用 --skip-processed：不写入 processed_weibo.json")

        return results

    def _save_to_quark(
        self,
        source_link: str,
        results: List[MovieInfo],
        weibo_id: str,
        image_urls: List[str],
    ) -> bool:
        """将结果转存到夸克网盘指定目录并重命名，并把微博图片一并上传。

        若目标目录已存在同名文件/文件夹，会先删除。只要有一失败就抛出异常。
        返回 True 表示确实执行了转存；False 表示没有有效的夸克 fid 可转存。
        """
        items = [
            {
                "fid": r.quark_fid,
                "file_name": r.chinese_name or "未命名",
                "share_file_name": r.quark_file_name,
                "final_name": r.generate_filename(),
            }
            for r in results
            if r.quark_fid
        ]
        if not items:
            logging.warning(f"微博 {weibo_id} 无有效夸克 fid，跳过转存")
            return False

        for item in items:
            logging.debug(
                f"  准备转存: fid={item['fid']}, "
                f"分享文件名={item.get('share_file_name')}, "
                f"目标名={item['final_name']}"
            )

        client = self.crawler.quark_client
        logging.info(f"开始转存 {len(items)} 项到 {self.save_dir}...")

        target_fid = client.find_or_create_dir(self.save_dir)
        if not target_fid:
            raise RuntimeError(f"无法找到或创建目标目录: {self.save_dir}")

        # 收集所有可能冲突的名称（分享最终名、原始分享名、微博图片名）
        conflict_names = set()
        for item in items:
            conflict_names.add(html.unescape(item["final_name"]))
            # 夸克不接受半角“/”，实际落盘名是替换成全角“／”的变体，一并纳入检测
            conflict_names.add(html.unescape(item["final_name"]).replace("/", "／"))
            share_name = item.get("share_file_name")
            if share_name:
                conflict_names.add(html.unescape(share_name))

        # 准备微博图片名称（如有），避免目标目录同名冲突
        image_name = None
        if image_urls:
            first_url = image_urls[0]
            ext = Path(urllib.parse.urlparse(first_url).path).suffix or ".jpg"
            image_name = f"{weibo_id}_img_1{ext}"
            conflict_names.add(image_name)

        # 删除目标目录中同名的文件/文件夹
        children = client.list_all_my_files(target_fid, size=100)
        conflicts = [
            child for child in children
            if html.unescape(child.get("file_name", "")) in conflict_names
        ]
        if conflicts:
            conflict_names_log = [c.get("file_name") for c in conflicts]
            logging.debug(f"目标目录已存在同名项，先删除: {conflict_names_log}")
            if not client.delete_files([c["fid"] for c in conflicts]):
                raise RuntimeError(f"删除目标目录同名项失败: {conflict_names_log}")

        save_results = client.save_and_rename(
            source_link,
            items,
            self.save_dir,
            lambda item: item.get("final_name"),
        )
        failed = [
            r for r in save_results
            if r.get("error") or not r.get("renamed")
        ]
        if failed:
            raise RuntimeError(f"转存或重命名失败: {failed}")

        logging.info(f"转存完成: {len(save_results)}/{len(save_results)} 项成功")

        # 上传微博配图到被转存的文件夹内（如果分享被保存为子文件夹）
        if image_name:
            final_names = {html.unescape(item["final_name"]) for item in items}
            image_target_fid = target_fid
            for child in client.list_all_my_files(target_fid, size=100):
                if (
                    html.unescape(child.get("file_name", "")) in final_names
                    and child.get("file_type") == 0
                ):
                    image_target_fid = child["fid"]
                    logging.debug(f"微博图片将上传到子文件夹: {child.get('file_name')}")
                    break

            # 配图是附属品：下载/上传失败只告警跳过，不影响已完成的转存结果，
            # 更不能中断整个运行（曾因网络瞬断在这里炸掉整晚批次）
            img_fid = None
            for attempt in range(3):
                try:
                    img_resp = self.crawler.session.get(first_url, timeout=30)
                    img_resp.raise_for_status()
                    img_fid = client.upload_file(
                        img_resp.content,
                        image_name,
                        image_target_fid,
                    )
                    break
                except Exception as e:
                    logging.warning(
                        f"微博图片下载/上传失败（第 {attempt + 1}/3 次）: {e}"
                    )
                    time.sleep(5)
            if img_fid:
                logging.info(f"微博图片上传成功: {image_name} (fid={img_fid})")
            else:
                logging.warning(f"微博图片多次失败，跳过: {image_name}")

        return True

    def run(self) -> List[MovieInfo]:
        """运行爬虫。"""
        logging.info(f"=== 龙虾启动 [目标日期: {self.target_date}] ===")
        start_time = time.perf_counter()

        for page in range(1, self.max_pages + 1):
            logging.info(f"获取第 {page} 页微博...")
            weibo_list = self.crawler.get_weibo_list(page)

            if not weibo_list:
                logging.info("没有更多微博")
                break

            for weibo in weibo_list:
                try:
                    infos = self.process_weibo(weibo)
                except Exception as e:
                    # 单条微博转存等失败不中断整个运行：
                    # 未标记已处理的微博下次运行会自动重试
                    logging.error(f"处理微博 [{weibo.get('id', weibo.get('mid', ''))}] 异常，跳过继续: {e}")
                    continue
                for info in infos:
                    self.results.append(info)
                    idx = len(self.results)
                    logging.info(f"✅ 提取成功 {idx}: {info.chinese_name or '未命名'}")
                    logging.info(f"   文件名: {info.generate_filename()}")
                    if info.source_link:
                        logging.info(f"   链接: {info.source_link}")

            # 时间线按时间倒序：该页微博全部早于目标日期说明已翻过目标，停止；
            # 只是没出现目标日期但仍有较新微博时应继续向后翻（回溯多天时需要）
            target_date_obj = datetime.strptime(self.target_date, "%Y-%m-%d").date()
            page_dates = [
                d
                for d in (
                    get_publish_date(w.get("created_at", w.get("timestamp", "")))
                    for w in weibo_list
                )
                if d is not None
            ]
            if page_dates and all(d < target_date_obj for d in page_dates):
                logging.info("该页微博全部早于目标日期，已翻过目标，停止")
                break

        self._save_results()
        elapsed = time.perf_counter() - start_time
        elapsed_str = self._format_elapsed(elapsed)
        logging.info(f"=== 完成，共处理 {len(self.results)} 条，耗时 {elapsed_str} ===")

        return self.results

    def _format_elapsed(self, seconds: float) -> str:
        """将秒数格式化为可读的中文耗时字符串。"""
        seconds = int(round(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}小时{minutes}分{secs}秒"
        if minutes:
            return f"{minutes}分{secs}秒"
        return f"{secs}秒"

    def _save_results(self) -> None:
        """保存结果到文件。"""
        Path(self.output_json).parent.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self.results]
        with open(self.output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"结果已保存: {self.output_json}")

        with open(self.output_txt, "w", encoding="utf-8") as f:
            for i, info in enumerate(self.results, 1):
                f.write(f"{i}. {info.generate_filename()}\n")
        logging.info(f"文件名列表已保存: {self.output_txt}")


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    logging.info(f"启动参数: uid={args.uid}, max_pages={args.max_pages}, target_date={args.target_date}")

    if not os.path.exists(args.config):
        logging.error(f"配置文件不存在: {args.config}")
        sys.exit(1)

    crawler = WeiboCrawler.from_config_file(args.config, uid=args.uid)

    lobster = Lobster(
        crawler=crawler,
        max_pages=args.max_pages,
        target_date=args.target_date,
        output_json=args.output_json,
        output_txt=args.output_txt,
        processed_file=args.processed_file,
        skip_processed=args.skip_processed,
        save_enabled=args.save,
        save_dir=args.save_dir,
    )
    run_start = time.perf_counter()
    results = lobster.run()
    elapsed = time.perf_counter() - run_start

    print(f"\n{'='*60}")
    print(f"目标日期提取结果 ({len(results)} 条)")
    print(f"{'='*60}")
    for i, info in enumerate(results, 1):
        # --save 时在电影名后标注转存情况
        marker = ""
        if args.save:
            marker = " （已转存）" if info.saved else " （未转存）"
        print(f"\n{i}. {info.chinese_name or '未命名'}{marker}")
        if info.foreign_name:
            print(f"   外文名: {info.foreign_name}")
        if info.director:
            print(f"   导演: {info.director}")
        if info.writer:
            print(f"   编剧: {info.writer}")
        if info.cast:
            print(f"   主演: {'/'.join(info.cast)}")
        if info.year:
            print(f"   年份: {info.year}")
        if info.awards:
            print(f"   获奖: {info.awards}")
        if info.rating:
            print(f"   评级: {info.rating}")
        if info.category:
            print(f"   类别: {info.category}")
        if info.language or info.subtitle:
            print(f"   语言: {info.language or ''}{info.subtitle or ''}")
        if info.season:
            print(f"   季数: 第{info.season}季")
        if info.episodes:
            print(f"   集数: 全{info.episodes}集")
        if info.source_link:
            print(f"   链接: {info.source_link}")
        print(f"   文件名: {info.generate_filename()}")

    print(f"\n总运行时间: {lobster._format_elapsed(elapsed)}")


if __name__ == "__main__":
    main()
