# -*- coding: utf-8 -*-
"""
MovieExtractor 单元测试
"""

import pytest

from extractor import MovieExtractor
from models import MovieInfo
from utils import parse_publish_time


@pytest.fixture
def extractor():
    return MovieExtractor()


class TestMovieExtractor:

    def test_extract_chinese_movie(self, extractor, sample_movie_weibo):
        info = extractor.extract(
            sample_movie_weibo["text"],
            sample_movie_weibo["id"],
            sample_movie_weibo["created_at"],
        )
        assert info is not None
        assert info.chinese_name == "肖申克的救赎"
        assert info.foreign_name == "The Shawshank Redemption"
        assert info.year == 1994
        assert "德拉邦特" in info.director
        assert "蒂姆·罗宾斯" in info.cast
        assert "摩根·弗里曼" in info.cast
        assert info.language == "国语"
        assert info.subtitle == "中字"
        assert info.genre == "电影"
        assert "改编自斯蒂芬·金《四季奇谭》" in info.awards
        assert "高分" in info.rating
        assert info.source_link is None  # 链接应由 crawler 提取

    def test_extract_documentary(self, extractor, sample_documentary_weibo):
        info = extractor.extract(
            sample_documentary_weibo["text"],
            sample_documentary_weibo["id"],
            sample_documentary_weibo["created_at"],
        )
        assert info is not None
        assert info.chinese_name == "地球脉动"
        assert info.genre == "纪录片"
        assert info.episodes == 11
        assert info.language == "英语"
        assert info.subtitle == "中英双字"
        assert info.rating == "高分"

    def test_extract_series_season_episodes(self, extractor, sample_series_weibo):
        info = extractor.extract(
            sample_series_weibo["text"],
            sample_series_weibo["id"],
            sample_series_weibo["created_at"],
        )
        assert info is not None
        assert info.chinese_name == "绝命毒师"
        assert info.genre == "剧集"
        assert info.season == 5
        assert info.episodes == 62
        assert "克兰斯顿" in info.cast[0]

    def test_extract_language_edge(self, extractor, sample_language_edge_weibo):
        info = extractor.extract(
            sample_language_edge_weibo["text"],
            sample_language_edge_weibo["id"],
            sample_language_edge_weibo["created_at"],
        )
        assert info is not None
        assert info.chinese_name == "寄生虫"
        assert info.language == "英韩语"
        assert info.subtitle == "中英双字"
        assert "奥斯卡最佳影片获奖作品" in info.awards

    def test_extract_language_with_distant_slash(self, extractor):
        # 回归：前文主演名单含斜杠（唐泽寿明/芦田爱菜）不应触发组合语言解析；
        # “已出日语中字”应提取为 日语/中字，而不是“已出日语”
        info = extractor.extract(
            "《推理竞技场》\n堤幸彦主演 唐泽寿明/芦田爱菜主演电影\n"
            "改编自深水黎一郎同名原著\n已出日语中字",
            "999",
            "2026-08-14",
        )
        assert info is not None
        assert info.language == "日语"
        assert info.subtitle == "中字"

    def test_extract_north_indian_language(self, extractor):
        # 回归：“北印度语”不在语言表时整个语言被丢弃只剩“中字”（水）
        info = extractor.extract(
            "《水》\n奥斯卡金像奖最佳外语片提名作品\n北印度语中字",
            "998",
            "2026-08-17",
        )
        assert info is not None
        assert info.language == "北印度语"
        assert info.subtitle == "中字"

    def test_extract_no_dialogue_pure_enjoyment(self, extractor):
        # 回归：时间的风景“无对白纯享”作为语言位置保留，“风光”为类别词
        info = extractor.extract(
            "《时间的风景》\n高分风光纪录片推荐\n无对白纯享",
            "997",
            "2026-08-17",
        )
        assert info is not None
        assert info.language == "无对白纯享"
        assert info.subtitle is None
        assert info.category == "风光/纪录"

    def test_director_posthumous_work(self, extractor):
        # 回归：“德里克·贾曼导演遗作”整体作为荣誉保留；
        # “遗作”不得被冒号兜底正则当成导演名（蓝）
        info = extractor.extract(
            "《蓝》\n德里克·贾曼导演遗作\n英语中英双字",
            "996",
            "2026-08-18",
        )
        assert info is not None
        assert info.director is None
        assert info.awards == "德里克·贾曼导演遗作"

    def test_extract_czech_slovak_language(self, extractor):
        # 回归：“捷克/斯洛伐克语”归一化为“捷克斯洛伐克语”（我的甜蜜家园）
        info = extractor.extract(
            "《我的甜蜜家园》\n奥斯卡金像奖最佳外语片提名作品\n"
            "伊日·门泽尔执导高分治愈电影\n捷克/斯洛伐克语中英双字",
            "995",
            "2026-08-18",
        )
        assert info is not None
        assert info.language == "捷克斯洛伐克语"
        assert info.subtitle == "中英双字"

    def test_foreign_season_suffix_merged_with_range(self):
        # 回归：叶卡捷琳娜大帝——外文名自带“Сезон 1”时，
        # 与生成的“1-4季”合并为“Сезон 1-4季”，不重复出现季数
        info = MovieInfo(
            chinese_name="叶卡捷琳娜大帝",
            foreign_name="Екатерина Сезон 1",
            season=4,
            season_raw="全4",
            raw_text="《叶卡捷琳娜大帝》\n热门高分传记历史剧集推荐\n全4季 俄语中字",
        )
        filename = info.generate_filename()
        assert filename.startswith("叶卡捷琳娜大帝 Екатерина Сезон 1-4季 （")

    def test_extract_short_film(self, extractor, sample_short_film_weibo):
        info = extractor.extract(
            sample_short_film_weibo["text"],
            sample_short_film_weibo["id"],
            sample_short_film_weibo["created_at"],
        )
        assert info is not None
        assert info.chinese_name == "调音师"
        assert info.genre == "短片"
        assert info.language == "法语"
        assert info.subtitle == "中字"

    def test_non_movie_content_filtered(self, extractor, sample_non_movie_weibo):
        assert extractor.is_non_movie_content(sample_non_movie_weibo["text"]) is True
        info = extractor.extract(
            sample_non_movie_weibo["text"],
            sample_non_movie_weibo["id"],
            sample_non_movie_weibo["created_at"],
        )
        assert info is None

    def test_invalid_cast_director_filtered(self, extractor, sample_invalid_cast_weibo):
        info = extractor.extract(
            sample_invalid_cast_weibo["text"],
            sample_invalid_cast_weibo["id"],
            sample_invalid_cast_weibo["created_at"],
        )
        assert info is not None
        assert info.chinese_name == "测试片"
        # "悬疑" 不应作为演员，"高分" 不应作为导演
        assert "悬疑" not in info.cast
        assert "高分" not in info.director if info.director else True

    def test_generate_filename_format(self, extractor, sample_movie_weibo):
        info = extractor.extract(
            sample_movie_weibo["text"],
            sample_movie_weibo["id"],
            sample_movie_weibo["created_at"],
        )
        filename = info.generate_filename()
        assert "肖申克的救赎" in filename
        assert "The Shawshank Redemption" in filename
        assert "1994" in filename
        assert "主演" in filename
        assert "导演" in filename
        assert "高分" in filename

    def test_generate_filename_no_data(self):
        info = MovieInfo()
        assert info.generate_filename() == "未命名"

    def test_extract_name_pair(self, extractor):
        cn, fn = extractor.extract_name_pair("《首》（Kubi）2023 北野武")
        assert cn == "首"
        assert fn == "Kubi"

    def test_extract_queer_palm_award(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武导演 戛纳电影节长片酷儿棕榈奖提名作品 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info is not None
        assert info.chinese_name == "首"
        assert "戛纳电影节长片酷儿棕榈奖提名作品" in info.awards

    def test_extract_self_written_directed_acted(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武自编自导自演 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info.director == "北野武"
        assert info.writer == "北野武"
        assert "北野武" in info.cast
        assert len(info.cast) == 1

    def test_extract_self_directed_acted(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武自导自演 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info.director == "北野武"
        assert info.writer is None
        assert "北野武" in info.cast

    def test_extract_self_written_directed(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武自编自导 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info.director == "北野武"
        assert info.writer == "北野武"
        assert not info.cast

    def test_generate_filename_combined_self_roles(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武自编自导自演 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "北野武自编自导自演" in filename
        # 不应重复出现单独的主演/导演/编剧
        assert "北野武主演" not in filename
        assert "北野武导演" not in filename
        assert "北野武编剧" not in filename

    def test_generate_filename_combined_director_cast(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武自导自演 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "北野武自导自演" in filename
        assert "北野武主演" not in filename
        assert "北野武导演" not in filename

    def test_generate_filename_combined_writer_director(self, extractor):
        info = extractor.extract(
            "《首》Kubi 2023 北野武自编自导 日语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "北野武自编自导" in filename
        assert "北野武导演" not in filename
        assert "北野武编剧" not in filename

    def test_movie_genre_displayed_as_pian(self, extractor):
        """电影类型在文件名中显示为“片”。"""
        info = extractor.extract(
            "《侠盗之星》\n纳塔温·崴唐缇派特主演动作犯罪片\n泰语中字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info is not None
        assert "犯罪动作片" in info.generate_filename()
        assert "犯罪动作电影" not in info.generate_filename()

    def test_year_not_duplicated_in_title(self, extractor):
        """标题中已含年份时文件名不再重复追加年份。"""
        info = extractor.extract(
            "《1975:天翻地覆的一年》\n冷门纪录片推荐\n英语中字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert filename.count("1975") == 1

    def test_award_trailing_genre_trimmed(self, extractor):
        """奖项末尾与类型重复时自动去重，避免“展映纪录片 纪录片”。"""
        info = extractor.extract(
            "《此街在何处？》\n洛迦诺电影节展映纪录片\n葡萄牙语中字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "洛迦诺电影节展映" in filename
        assert "展映纪录片 纪录片" not in filename

    def test_season_extra_with_premiere_info(self, extractor):
        """第X季首播信息应完整捕获到文件名中。"""
        info = extractor.extract(
            "《女警出更》\n最新冷门悬疑犯罪剧集推荐\n第二季首播至第一集\n含中字第一季\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "第二季首播至第一集" in filename
        assert "含中字第一季" in filename

    def test_title_trailing_season_digit_split(self, extractor):
        """标题末尾的季节数字应拆分为“1-N季”，括号内同时保留原季节描述。"""
        info = extractor.extract(
            "《杀人者的购物中心2》\n李栋旭/金慧埈主演动作悬疑剧集\n全两季 韩语中字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "杀人者的购物中心 1-2季" in filename
        assert "杀人者的购物中心2" not in filename
        assert "全2季" in filename
        assert "第2季" not in filename

    def test_title_trailing_chinese_season_word_split(self, extractor):
        """标题末尾的中文“X季”应拆分为“1-N季”，括号内同时保留原季节描述。"""
        info = extractor.extract(
            "《切尔西侦探》\n冷门悬疑犯罪剧集推荐\n全3季 英语中字\n见平👇",
            "123",
            "2026-08-13 10:00:00",
        )
        # 模拟夸克文件名带回的中文季数后缀
        info.chinese_name = "切尔西侦探三季"
        filename = info.generate_filename()
        assert "切尔西侦探 1-3季" in filename
        assert "切尔西侦探三季" not in filename
        assert "全3季" in filename
        assert "第3季" not in filename

    def test_english_spanish_language_extracted(self, extractor):
        """英/西语应正确识别为英西语。"""
        info = extractor.extract(
            "《锦绣山河烈士血》\n奥斯卡金像奖最佳影片提名作品\n约翰·韦恩自导自演作品\n英/西语中字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info is not None
        assert info.language == "英西语"

    def test_cannes_un_certain_regard_grand_prize(self, extractor):
        """戛纳电影节一种关注大奖提名作品应被提取。"""
        info = extractor.extract(
            "《萨拉米的士兵》\n戛纳电影节一种关注大奖提名作品\n西班牙语中英双字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info is not None
        assert "戛纳电影节一种关注大奖提名作品" in info.awards

    def test_psychological_category_order(self, extractor):
        """心理类别应排在纪录之前。"""
        info = extractor.extract(
            "《你看不见的我》\n高分心理纪录剧集推荐\n全5集 英语中字\n见平👇",
            "123",
            "2026-08-12 10:00:00",
        )
        filename = info.generate_filename()
        assert "心理纪录剧集" in filename

    def test_season_extra_with_movie(self, extractor):
        """全X季+电影应完整捕获到文件名中。"""
        info = extractor.extract(
            "《飞出个未来》\n热门高分动画推荐\n全13季+电影 英语中字\n见平👇",
            "123",
            "2026-08-13 10:00:00",
        )
        assert info is not None
        assert info.season_extra == "全13季+电影"
        filename = info.generate_filename()
        assert "全13季+电影" in filename
        assert "全13季 英语中字" not in filename

    def test_adaptation_without_book_title_and_year_ban(self, extractor):
        """改编自无书名形式时应捕获完整描述，年份不重复拼到标题。"""
        info = extractor.extract(
            "《大师与玛格丽特》\n改编自同名高分原著\n2024版 俄语中英双字\n见平👇",
            "123",
            "2026-08-13 10:00:00",
        )
        assert info is not None
        assert "改编自同名高分原著" in info.awards
        assert "2024" in info.awards
        filename = info.generate_filename()
        assert "大师与玛格丽特 2024" not in filename
        assert "（改编自同名高分原著 2024版 俄语中英双字）" in filename

    def test_english_lithuanian_language_extracted(self, extractor):
        """英/立陶宛语应正确识别为英立陶宛语。"""
        info = extractor.extract(
            "《峡谷》\n安雅·泰勒-乔伊/迈尔斯·特勒主演动作科幻片\n英/立陶宛语中英双字\n见平👇",
            "123",
            "2026-08-13 10:00:00",
        )
        assert info is not None
        assert info.language == "英立陶宛语"
        assert info.subtitle == "中英双字"
        assert "英立陶宛语中英双字" in info.generate_filename()

    def test_nested_guillemets_title_and_reality_show(self, extractor):
        """嵌套书名号应提取外层完整标题，真人秀类型与冒险类别应正确识别。"""
        info = extractor.extract(
            "《《拣选》剧组与贝尔·格里尔斯一起荒野求生》\n最新冷门冒险真人秀推荐\n全6集 英语中英双字\n见平👇",
            "123",
            "2026-08-13 10:00:00",
        )
        assert info is not None
        assert info.chinese_name == "《拣选》剧组与贝尔·格里尔斯一起荒野求生"
        assert info.genre == "真人秀"
        assert "冒险" in info.category
        assert "冷门冒险真人秀" in info.generate_filename()

    def test_parse_publish_time(self):
        from datetime import datetime
        from unittest.mock import patch

        # mock 当前时间为 2026-08-13，使“昨天”对应 2026-08-12
        with patch("utils.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 13, 12, 0, 0)
            mock_dt.strptime = datetime.strptime
            mock_dt.fromtimestamp = datetime.fromtimestamp
            from utils import parse_publish_time
            assert parse_publish_time("2026-08-12 10:00:00", "2026-08-12") is True
            assert parse_publish_time("2026-08-11 10:00:00", "2026-08-12") is False
            ts = datetime(2026, 8, 12, 10, 0, 0).timestamp()
            assert parse_publish_time(ts, "2026-08-12") is True
            assert parse_publish_time("昨天", "2026-08-12") is True
            assert parse_publish_time("昨天", "2026-08-11") is False
            assert parse_publish_time(None, "2026-08-12") is False

    def test_douban_rating_at_end_of_filename(self, extractor):
        """豆瓣评分应出现在括号内最后（紧挨右括号）。"""
        info = extractor.extract(
            "《肖申克的救赎》1994 弗兰克·德拉邦特导演 蒂姆·罗宾斯主演 国语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        info.douban_rating = "豆瓣9.7"
        filename = info.generate_filename()
        # 豆瓣评分应在语言字幕之后、右括号之前
        assert filename.endswith("国语中字 豆瓣9.7）")

    def test_colon_in_chinese_name_normalized(self, extractor):
        """中文片名中的半角冒号应转为全角冒号，并去掉两侧空格。"""
        info = extractor.extract(
            "《某片: 副标题》2020 国语中字",
            "123",
            "2026-08-12 10:00:00",
        )
        assert info.chinese_name == "某片：副标题"
        filename = info.generate_filename()
        assert "某片：" in filename
        assert ":" not in filename

    def test_html_entities_in_foreign_name_decoded(self):
        """外文片名中的 HTML 实体应被解码（如 &amp; -> &）。"""
        info = MovieInfo(
            chinese_name="路德灵异侦探社",
            foreign_name="Lockwood &amp; Co.",
            year=2023,
        )
        assert info.foreign_name == "Lockwood & Co."
        filename = info.generate_filename()
        assert "Lockwood & Co." in filename
        assert "&amp;" not in filename

    def test_html_entities_in_chinese_name_decoded(self):
        """中文片名中的 HTML 实体也应被解码。"""
        info = MovieInfo(chinese_name="测试&amp;片", year=2020)
        assert info.chinese_name == "测试&片"
