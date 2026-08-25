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

    def test_extract_japan_academy_award_animation(self, extractor):
        # 回归：日本电影学院奖最佳动画片提名作品（烟囱小镇的普佩尔）
        info = extractor.extract(
            "《烟囱小镇的普佩尔》\n日本电影学院奖最佳动画片提名作品\n国日双语中字",
            "994",
            "2026-08-18",
        )
        assert info is not None
        assert info.awards == "日本电影学院奖最佳动画片提名作品"
        assert info.language == "国日双语"

    def test_extract_chinese_english_bilingual_language(self, extractor):
        # 回归：“国英双语”作为组合语言识别（大卫·科波菲尔）
        info = extractor.extract(
            "《大卫·科波菲尔》\n改编自狄更斯同名高分原著\n全两集 国英双语中字",
            "993",
            "2026-08-18",
        )
        assert info is not None
        assert info.language == "国英双语"
        assert info.subtitle == "中字"
        assert info.episodes == 2

    def test_extract_khmer_language(self, extractor):
        # 回归：高棉语（无影医魂）
        info = extractor.extract(
            "《无影医魂》\n最新冷门恐怖电影推荐\n已出高棉语中字",
            "992",
            "2026-08-18",
        )
        assert info is not None
        assert info.language == "高棉语"
        assert info.subtitle == "中字"

    def test_extract_spanish_german_russian_slash_language(self, extractor):
        # 回归：“西班牙/德/俄语”归一化为“西班牙德俄语”（你梦中的姑娘）
        info = extractor.extract(
            "《你梦中的姑娘》\n佩内洛普·克鲁兹主演电影\n西班牙/德/俄语中字",
            "991",
            "2026-08-18",
        )
        assert info is not None
        assert info.language == "西班牙德俄语"
        assert info.subtitle == "中字"

    def test_extract_greek_german_english_slash_language(self, extractor):
        # 回归：“希腊/德/英语”归一化为“希腊德英语”，
        # 不得被“德/英语”替换拆开而丢掉希腊（音乐）
        info = extractor.extract(
            "《音乐》\n柏林电影节金熊奖提名作品\n安格拉·夏娜莱克导演作品\n希腊/德/英语中英双字",
            "990",
            "2026-08-18",
        )
        assert info is not None
        assert info.language == "希腊德英语"
        assert info.subtitle == "中英双字"

    def test_extract_japanese_new_wave_work(self, extractor):
        # 回归：“日本新浪潮电影作品”作为描述性荣誉保留（洲崎天堂红灯区）
        info = extractor.extract(
            "《洲崎天堂红灯区》\n川岛雄三执导 新珠三千代主演电影\n"
            "日本新浪潮电影作品\n日语中字",
            "987",
            "2026-08-18",
        )
        assert info is not None
        assert info.director == "川岛雄三"
        assert info.cast == ["新珠三千代"]
        assert info.awards == "日本新浪潮电影作品"

    def test_extract_golden_horse_actress_award(self, extractor):
        # 回归：金马最佳女主角获奖作品（回光奏鸣曲）
        info = extractor.extract(
            "《回光奏鸣曲》\n洛迦诺电影节当代电影人单元金豹奖提名作品\n"
            "金马最佳女主角获奖作品\n陈湘琪主演电影\n国语中字",
            "986",
            "2026-08-19",
        )
        assert info is not None
        assert info.awards == "洛迦诺电影节当代电影人单元金豹奖提名作品 金马最佳女主角获奖作品"

    def test_extract_shan_language(self, extractor):
        # 回归：掸语（魂歌）
        info = extractor.extract(
            "《魂歌》\n冷门纪录片推荐\n掸语中字",
            "985",
            "2026-08-19",
        )
        assert info is not None
        assert info.language == "掸语"
        assert info.subtitle == "中字"

    def test_extract_costume_drama_category(self, extractor):
        # 回归：古装作为类别词，顺序在喜剧之后（王后伞下）
        info = extractor.extract(
            "《王后伞下》\n金惠秀主演高分喜剧古装剧集\n全16集 韩语中字",
            "984",
            "2026-08-19",
        )
        assert info is not None
        assert info.category == "喜剧/古装"
        filename = info.generate_filename()
        assert "高分喜剧古装剧集" in filename

    def test_extract_talk_show_genre(self, extractor):
        # 回归：访谈节目作为类型（怪奇背后）
        info = extractor.extract(
            "《怪奇背后》\n冷门高分访谈节目推荐\n全7集 英语中字",
            "983",
            "2026-08-19",
        )
        assert info is not None
        assert info.genre == "访谈节目"
        filename = info.generate_filename()
        assert "冷门高分访谈节目" in filename

    def test_extract_berlin_forum_caligari_award(self, extractor):
        # 回归：柏林电影节论坛单元卡里加里奖（想起所有夜晚）
        info = extractor.extract(
            "《想起所有夜晚》\n柏林电影节论坛单元卡里加里奖提名作品\n日语中字",
            "982",
            "2026-08-19",
        )
        assert info is not None
        assert info.awards == "柏林电影节论坛单元卡里加里奖提名作品"

    def test_extract_berlin_best_doc_redundant_jian(self, extractor):
        # 回归：“柏林电影节最佳纪录片奖获奖作品”去掉与“获奖”重复的“奖”
        # （缅甸日记）；语言缅甸语；genre 纪录片因奖项已含“纪录”而隐藏
        info = extractor.extract(
            "《缅甸日记》\n柏林电影节最佳纪录片奖获奖作品\n缅甸语中字",
            "981",
            "2026-08-19",
        )
        assert info is not None
        assert info.awards == "柏林电影节最佳纪录片获奖作品"
        assert info.language == "缅甸语"
        filename = info.generate_filename()
        assert "柏林电影节最佳纪录片获奖作品 缅甸语中字" in filename
        assert "纪录片 " not in filename

    def test_extract_animated_movie_genre(self, extractor):
        # 回归：动画电影类型显示为“动画片”（猎魔人：深渊海妖）
        info = extractor.extract(
            "《猎魔人：深渊海妖》\n冷门动作奇幻冒险动画电影推荐\n英语中英双字",
            "980",
            "2026-08-19",
        )
        assert info is not None
        assert info.genre == "动画片"
        filename = info.generate_filename()
        assert "冷门奇幻动作冒险动画片" in filename

    def test_extract_variety_show_episode_arabic(self, extractor):
        # 回归：综艺“首播至第五期”期数转阿拉伯数字“首播至第5期”（你为什么要爬山？）；
        # 剧集“首播至第一集”保持中文数字（绿灯军团）
        info = extractor.extract(
            "《你为什么要爬山？》\n最新热门真人秀推荐\n首播至第五期",
            "989",
            "2026-08-18",
        )
        assert info is not None
        assert info.season_extra == "首播至第5期"
        filename = info.generate_filename()
        assert "热门真人秀 首播至第5期" in filename

        info2 = extractor.extract(
            "《绿灯军团》\n最新热门动作科幻剧集推荐\n首播至第一集",
            "988",
            "2026-08-18",
        )
        assert info2 is not None
        assert info2.season_extra == "首播至第一集"

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

    def test_extract_related_tag_prefix(self, extractor):
        # 回归：“哈利·波特相关”描述前缀到类别段最前（再见，霍格沃茨）
        info = extractor.extract(
            "《再见，霍格沃茨》\n哈利·波特相关高分纪录片\n英语中英双字",
            "5334108167476228",
            "2026-08-20",
        )
        assert info is not None
        assert info.related_tag == "哈利·波特相关"
        assert info.genre == "纪录片"
        filename = info.generate_filename()
        assert "哈利·波特相关高分纪录片" in filename

    def test_extract_bafta_best_british_film_award(self, extractor):
        # 回归：英国电影学院奖最佳英国影片提名作品（发掘）
        info = extractor.extract(
            "《发掘》\n凯瑞·穆里根/拉尔夫·费因斯/莉莉·詹姆斯主演\n"
            "英国电影学院奖最佳英国影片提名作品\n热门高分传记历史电影推荐\n英语中字",
            "5334087736755867",
            "2026-08-20",
        )
        assert info is not None
        assert info.awards == "英国电影学院奖最佳英国影片提名作品"

    def test_extract_karlovy_vary_crystal_globe_award(self, extractor):
        # 回归：卡罗维发利电影节水晶地球仪奖最佳影片提名作品（催眠）
        info = extractor.extract(
            "《催眠》\n卡罗维发利电影节水晶地球仪奖最佳影片提名作品\n瑞典语中英双字",
            "5334067505266702",
            "2026-08-20",
        )
        assert info is not None
        assert info.awards == "卡罗维发利电影节水晶地球仪奖最佳影片提名作品"
        assert info.language == "瑞典语"

    def test_extract_sp_genre(self, extractor):
        # 回归：日剧特别篇“SP”作为类型替代默认“片”（吃饱睡足等幸福）
        info = extractor.extract(
            "《吃饱睡足等幸福～早春养生篇～》\n最新热门治愈SP推荐\n已出日语中日双字",
            "5333937555769969",
            "2026-08-20",
        )
        assert info is not None
        assert info.genre == "SP"
        assert info.category == "治愈"
        filename = info.generate_filename()
        assert "热门治愈SP" in filename

    def test_extract_golden_horse_short_film_award(self, extractor):
        # 回归：金马最佳剧情短片获奖作品（讲话没有在听）；
        # 类别词“剧情”“短片”已含于奖项，不再重复显示
        info = extractor.extract(
            "《讲话没有在听》\n金马最佳剧情短片获奖作品\n国/闽南语中英双字",
            "5334458837243454",
            "2026-08-21",
        )
        assert info is not None
        assert info.awards == "金马最佳剧情短片获奖作品"
        assert info.category is None
        filename = info.generate_filename()
        assert "金马最佳剧情短片获奖作品 国闽南语中英双字" in filename
        # “剧情”“短片”不作为独立类别段出现（奖项内含不算）
        assert " 剧情" not in filename
        assert "短片 " not in filename

    def test_extract_golden_globe_award(self, extractor):
        # 回归：金球奖最佳剧情片提名作品（曼克）；类别“剧情”已含于奖项
        info = extractor.extract(
            "《曼克》\n加里·奥德曼/阿曼达·塞弗里德/莉莉·柯林斯主演\n"
            "金球奖最佳剧情片提名作品\n大卫·芬奇导演作品\n英语中英双字",
            "5334294081046109",
            "2026-08-21",
        )
        assert info is not None
        assert info.awards == "金球奖最佳剧情片提名作品"
        assert info.category is None
        filename = info.generate_filename()
        assert "金球奖最佳剧情片提名作品 英语中英双字" in filename
        assert "剧情片" not in filename.replace("金球奖最佳剧情片提名作品", "")

    def test_extract_rotterdam_award(self, extractor):
        # 回归：鹿特丹电影节大银幕奖提名作品（世界的阿菊）
        info = extractor.extract(
            "《世界的阿菊》\n鹿特丹电影节大银幕奖提名作品\n黑木华主演 阪本顺治导演作品\n日语中日双字",
            "5334295568990369",
            "2026-08-21",
        )
        assert info is not None
        assert info.awards == "鹿特丹电影节大银幕奖提名作品"
        assert info.director == "阪本顺治"

    def test_extract_golden_globe_foreign_film_award(self, extractor):
        # 回归：金球奖最佳外语片获奖作品（孩子的眼睛）
        info = extractor.extract(
            "《孩子的眼睛》\n金球奖最佳外语片获奖作品\n高峰秀子主演电影\n日语中字",
            "5334481464462451",
            "2026-08-21",
        )
        assert info is not None
        assert info.awards == "金球奖最佳外语片获奖作品"
        filename = info.generate_filename()
        assert "高峰秀子主演 金球奖最佳外语片获奖作品 日语中字" in filename

    def test_extract_berlin_panorama_award_and_lang(self, extractor):
        # 回归：柏林电影节全景单元最佳影片获奖作品 + 法/英/挪威语（迷情漩涡）
        info = extractor.extract(
            "《迷情漩涡》\n柏林电影节全景单元最佳影片获奖作品\n丹尼斯·维伦纽瓦导演作品\n法/英/挪威语中字",
            "5334821383442534",
            "2026-08-22",
        )
        assert info is not None
        assert info.awards == "柏林电影节全景单元最佳影片获奖作品"
        assert info.language == "法英挪威语"
        assert info.subtitle == "中字"

    def test_extract_chinese_subtitle_only(self, extractor):
        # 回归：仅“中文字幕”无语言词时仍提取字幕（金钱骗局）
        info = extractor.extract(
            "《金钱骗局》\n冷门高分惊悚犯罪剧集推荐\n全8集 中文字幕",
            "5334820649701447",
            "2026-08-22",
        )
        assert info is not None
        assert info.language is None
        assert info.subtitle == "中文字幕"
        filename = info.generate_filename()
        assert "全8集 中文字幕 豆瓣" in filename or "全8集 中文字幕" in filename

    def test_extract_musical_category(self, extractor):
        # 回归：“歌舞”作为类别词，顺序在喜剧之后（玛蒂尔达：音乐剧）
        info = extractor.extract(
            "《玛蒂尔达:音乐剧》\n高分喜剧歌舞片推荐\n英语中英双字",
            "5334779378534952",
            "2026-08-22",
        )
        assert info is not None
        assert info.category == "喜剧/歌舞"
        filename = info.generate_filename()
        assert "高分喜剧歌舞片" in filename

    def test_extract_wordless_short_film_genre(self, extractor):
        # 回归：“无对白短片”连写作为整体类型（蚁蛉）
        info = extractor.extract(
            "《蚁蛉》\n克里斯托弗·诺兰导演作品\n无对白短片",
            "5334716564902130",
            "2026-08-22",
        )
        assert info is not None
        assert info.genre == "无对白短片"
        filename = info.generate_filename()
        assert "克里斯托弗·诺兰导演 无对白短片" in filename

    def test_extract_berlin_encounters_award_wordless_doc(self, extractor):
        # 回归：柏林电影节遇见单元最佳影片提名作品 + “无对白纪录片”（贡达）
        info = extractor.extract(
            "《贡达》\n柏林电影节遇见单元最佳影片提名作品\n无对白纪录片",
            "5334700230971683",
            "2026-08-22",
        )
        assert info is not None
        assert info.awards == "柏林电影节遇见单元最佳影片提名作品"
        assert info.genre == "无对白纪录片"
        filename = info.generate_filename()
        assert "柏林电影节遇见单元最佳影片提名作品 无对白纪录片" in filename

    def test_wordless_pure_enjoy_not_merged_into_genre(self, extractor):
        # 回归：“无对白纯享”不带类型词，仍走语言位置（时间的风景）
        info = extractor.extract(
            "《时间的风景》\n高分风光纪录片推荐\n无对白纯享",
            "5334077000000001",
            "2026-08-17",
        )
        assert info is not None
        assert info.genre == "纪录片"
        assert info.language == "无对白纯享"
        filename = info.generate_filename()
        assert "高分风光纪录片 无对白纯享" in filename

    def test_extract_czech_film_history_honor(self, extractor):
        # 回归：捷克影史第一佳片描述性荣誉（玛婕妲·拉扎洛娃）
        info = extractor.extract(
            "《玛婕妲·拉扎洛娃》\n捷克影史第一佳片\n捷克语中字",
            "5334457741740217",
            "2026-08-21",
        )
        assert info is not None
        assert info.awards == "捷克影史第一佳片"
        assert info.language == "捷克语"

    def test_extract_director_debut_feature(self, extractor):
        # 回归：“X导演长片首作”整体保留（追随），“首作”不作为导演名
        info = extractor.extract(
            "《追随》\n克里斯托弗·诺兰导演长片首作\n高分悬疑惊悚犯罪片推荐\n英语中英双字",
            "5334356604223720",
            "2026-08-21",
        )
        assert info is not None
        assert info.awards == "克里斯托弗·诺兰导演长片首作"
        assert info.director is None
        filename = info.generate_filename()
        assert "克里斯托弗·诺兰导演长片首作 高分悬疑惊悚犯罪片" in filename

    def test_extract_english_spanish_slash_language(self, extractor):
        # 回归：英/西班牙语 → 英西班牙语（菜单）
        info = extractor.extract(
            "《菜单》\n拉尔夫·费因斯/安雅·泰勒-乔伊/尼古拉斯·霍尔特主演\n"
            "热门喜剧惊悚恐怖片推荐\n英/西班牙语中英双字",
            "5334436262712859",
            "2026-08-21",
        )
        assert info is not None
        assert info.language == "英西班牙语"
        assert info.subtitle == "中英双字"

    def test_extract_english_japanese_slash_language(self, extractor):
        # 回归：英/日语 → 英日语（沉默）
        info = extractor.extract(
            "《沉默》\n安德鲁·加菲尔德/亚当·德赖弗/连姆·尼森主演电影\n"
            "改编自远藤周作同名高分原著\n马丁·斯科塞斯导演作品\n英/日语中字",
            "5334341559517242",
            "2026-08-21",
        )
        assert info is not None
        assert info.language == "英日语"
        assert info.subtitle == "中字"

    def test_extract_cantonese_mandarin_western_language(self, extractor):
        # 回归：粤/国/西语 → 粤国西语（摄氏零度·春光再现）
        info = extractor.extract(
            "《摄氏零度·春光再现》\n热门高分纪录片推荐\n粤/国/西语中字",
            "5334281616097453",
            "2026-08-21",
        )
        assert info is not None
        assert info.language == "粤国西语"
        assert info.subtitle == "中字"

    def test_extract_french_serbian_slash_language(self, extractor):
        # 回归：法/塞尔维亚语 → 法塞尔维亚语（狂喜）
        info = extractor.extract(
            "《狂喜》\n戛纳电影节金摄影机奖提名作品\n法/塞尔维亚语中英双字",
            "5334435672363926",
            "2026-08-21",
        )
        assert info is not None
        assert info.language == "法塞尔维亚语"
        assert info.subtitle == "中英双字"

    def test_extract_french_german_with_cn_fr_subtitle(self, extractor):
        # 回归：法/德语 + 中法双字 → 法德语中法双字（同路前行）
        info = extractor.extract(
            "《同路前行》\n冷门冒险电影推荐\n法/德语中法双字",
            "5334417096314116",
            "2026-08-21",
        )
        assert info is not None
        assert info.language == "法德语"
        assert info.subtitle == "中法双字"

    def test_extract_georgian_language(self, extractor):
        # 回归：格鲁吉亚语（然后我们跳了舞）
        info = extractor.extract(
            "《然后我们跳了舞》\n戛纳电影节酷儿棕榈奖提名作品\n格鲁吉亚语中字",
            "5334410000000001",
            "2026-08-21",
        )
        assert info is not None
        assert info.language == "格鲁吉亚语"
        assert info.subtitle == "中字"

    def test_four_cast_members_kept(self, extractor):
        # 回归：主演最多保留 4 人（不久，就要永别了）
        info = extractor.extract(
            "《不久，就要永别了》\n滨边美波/目黑莲/古川琴音/北村匠海主演电影\n已出日语中日双字",
            "5334298223709310",
            "2026-08-21",
        )
        assert info is not None
        assert len(info.cast) == 4
        filename = info.generate_filename()
        assert "滨边美波、目黑莲、古川琴音、北村匠海主演" in filename

    def test_extract_busan_new_currents_award(self, extractor):
        # 回归：釜山电影节新浪潮奖获奖作品（负罪少女）
        info = extractor.extract(
            "《负罪少女》\n釜山电影节新浪潮奖获奖作品\n韩语中字",
            "5335300000000001",
            "2026-08-23",
        )
        assert info is not None
        assert info.awards == "釜山电影节新浪潮奖获奖作品"
        assert info.language == "韩语"
        assert info.subtitle == "中字"

    def test_extract_cannes_critics_week_award_malay(self, extractor):
        # 回归：戛纳电影节影评人周单元大奖获奖作品 + 马来语（虎纹少女）
        info = extractor.extract(
            "《虎纹少女》\n戛纳电影节影评人周单元大奖获奖作品\n马来语中字",
            "5335300000000002",
            "2026-08-23",
        )
        assert info is not None
        assert info.awards == "戛纳电影节影评人周单元大奖获奖作品"
        assert info.language == "马来语"
        assert info.subtitle == "中字"

    def test_extract_berlin_encounters_best_director_multilingual(self, extractor):
        # 回归：柏林遇见单元最佳导演 + 多语（马尔姆克罗格庄园）；
        # 程序惯例：角色在前、奖项在后，“最佳导演获奖”不加冗余“奖”
        info = extractor.extract(
            "《马尔姆克罗格庄园》\n柏林电影节遇见单元最佳导演获奖作品\n克利斯提·普优导演作品\n多语中字",
            "5335300000000003",
            "2026-08-23",
        )
        assert info is not None
        assert info.awards == "柏林电影节遇见单元最佳导演获奖作品"
        assert info.director == "克利斯提·普优"
        assert info.language == "多语"
        assert info.subtitle == "中字"
        filename = info.generate_filename()
        assert "克利斯提·普优导演 柏林电影节遇见单元最佳导演获奖作品 多语中字" in filename

    def test_extract_producer_tag_standalone_segment(self, extractor):
        # 回归：A24出品作为独立段落置于获奖之后（杨之后）
        info = extractor.extract(
            "《杨之后》\n科林·法瑞尔主演 郭共达执导 A24出品科幻片\n"
            "戛纳电影节一种关注大奖提名作品\n英语中英双字",
            "5335300000000004",
            "2026-08-23",
        )
        assert info is not None
        assert info.producer_tag == "A24出品"
        filename = info.generate_filename()
        assert "戛纳电影节一种关注大奖提名作品 A24出品 科幻片" in filename

    def test_extract_work_credit_without_director_word(self, extractor):
        # 回归：“佩德罗·阿莫多瓦作品”不带“导演”字样的主创署名，
        # 排在主演之后、获奖之前（奇怪的生活方式）
        info = extractor.extract(
            "《奇怪的生活方式》\n佩德罗·帕斯卡/伊桑·霍克主演 佩德罗·阿莫多瓦作品\n"
            "戛纳电影节短片酷儿棕榈奖提名作品\n中英双字",
            "5335300000000005",
            "2026-08-23",
        )
        assert info is not None
        assert info.work_credit == "佩德罗·阿莫多瓦作品"
        filename = info.generate_filename()
        assert "佩德罗·帕斯卡、伊桑·霍克主演 佩德罗·阿莫多瓦作品 戛纳电影节短片酷儿棕榈奖提名作品" in filename

    def test_work_credit_skipped_for_director_word(self, extractor):
        # 回归：“X导演作品”“自导自演作品”不作为“X作品”署名（已由导演/组合角色提取）
        info = extractor.extract(
            "《触礁》\n索菲亚·科波拉导演作品\n英语中字",
            "5335300000000006",
            "2026-08-14",
        )
        assert info is not None
        assert info.work_credit is None
        assert info.director == "索菲亚·科波拉"
        info2 = extractor.extract(
            "《首》\n北野武自导自演作品\n日语中字",
            "5335300000000007",
            "2026-08-13",
        )
        assert info2 is not None
        assert info2.work_credit is None
        assert info2.director == "北野武"

    def test_extract_san_sebastian_jury_special_prize(self, extractor):
        # 回归：圣塞巴斯蒂安电影节主竞赛单元评审团特别奖获奖作品（佛在耻辱中倒塌）
        info = extractor.extract(
            "《佛在耻辱中倒塌》\n圣塞巴斯蒂安电影节主竞赛单元评审团特别奖获奖作品\n波斯语中英双字",
            "5335300000000008",
            "2026-08-23",
        )
        assert info is not None
        assert info.awards == "圣塞巴斯蒂安电影节主竞赛单元评审团特别奖获奖作品"
        assert info.language == "波斯语"
        assert info.subtitle == "中英双字"

    def test_extract_french_arabic_english_slash_language(self, extractor):
        # 回归：法/阿拉伯/英语 → 法阿拉伯英语（焦土之城）
        info = extractor.extract(
            "《焦土之城》\n丹尼斯·维伦纽瓦导演作品\n法/阿拉伯/英语中字",
            "5335300000000009",
            "2026-08-23",
        )
        assert info is not None
        assert info.language == "法阿拉伯英语"
        assert info.subtitle == "中字"

    def test_extract_german_russian_slash_language(self, extractor):
        # 回归：德/俄语 → 德俄语（无主之作）
        info = extractor.extract(
            "《无主之作》\n威尼斯电影节金狮奖提名作品\n德/俄语中字",
            "5335300000000010",
            "2026-08-23",
        )
        assert info is not None
        assert info.language == "德俄语"
        assert info.subtitle == "中字"

    def test_extract_tongying_genre(self, extractor):
        # 回归：“同影”作为类型词，与类别连写（大男孩）
        info = extractor.extract(
            "《大男孩》\n最新冷门喜剧同影推荐\n已出英语中字",
            "5335400000000001",
            "2026-08-24",
        )
        assert info is not None
        assert info.genre == "同影"
        assert info.category == "喜剧"
        filename = info.generate_filename()
        assert "冷门喜剧同影" in filename

    def test_extract_english_portuguese_german_slash_language(self, extractor):
        # 回归：英/葡/德语 → 英葡德语（里斯本的故事）
        info = extractor.extract(
            "《里斯本的故事》\n维姆·文德斯执导高分电影\n英/葡/德语中字",
            "5335400000000002",
            "2026-08-24",
        )
        assert info is not None
        assert info.language == "英葡德语"
        assert info.subtitle == "中字"

    def test_extract_cesar_best_foreign_film_award(self, extractor):
        # 回归：法国凯撒电影奖最佳外语片提名作品（黑水）
        info = extractor.extract(
            "《黑水》\n马克·鲁法洛/安妮·海瑟薇/蒂姆·罗宾斯主演电影\n"
            "法国凯撒电影奖最佳外语片提名作品\n托德·海因斯导演高分作品\n英语中英双字",
            "5335400000000003",
            "2026-08-24",
        )
        assert info is not None
        assert info.awards == "法国凯撒电影奖最佳外语片提名作品"
        assert info.director == "托德·海因斯"
        filename = info.generate_filename()
        assert "法国凯撒电影奖最佳外语片提名作品 高分片" in filename

    def test_extract_russian_english_german_slash_language(self, extractor):
        # 回归：俄/英/德语 → 俄英德语（纳瓦尔尼）；注意不能被“英/德语”抢先替换
        info = extractor.extract(
            "《纳瓦尔尼》\n奥斯卡金像奖最佳纪录长片获奖作品\n俄/英/德语中字",
            "5335400000000004",
            "2026-08-24",
        )
        assert info is not None
        assert info.language == "俄英德语"
        assert info.subtitle == "中字"

    def test_extract_venice_future_digital_film_award(self, extractor):
        # 回归：威尼斯电影节未来数字电影奖获奖作品（白痴）
        info = extractor.extract(
            "《白痴》\n威尼斯电影节未来数字电影奖获奖作品\n浅野忠信主演高分电影\n日语中字",
            "5335600000000001",
            "2026-08-25",
        )
        assert info is not None
        assert info.awards == "威尼斯电影节未来数字电影奖获奖作品"
        filename = info.generate_filename()
        assert "浅野忠信主演 威尼斯电影节未来数字电影奖获奖作品 高分片" in filename

    def test_extract_three_language_compound(self, extractor):
        # 回归：英日国三语 作为整体语言（海贼王真人版）
        info = extractor.extract(
            "《海贼王(真人版）》\n热门高分奇幻动作剧集推荐\n全两季 英日国三语中字",
            "5335600000000002",
            "2026-08-25",
        )
        assert info is not None
        assert info.language == "英日国三语"
        assert info.subtitle == "中字"

    def test_extract_supervisor_and_quan_director(self, extractor):
        # 回归：监制署名按原文位置插入角色段；导演名可含“全”字（范保德）
        info = extractor.extract(
            "《范保德》\n台北电影奖最佳剧情长片提名作品\n侯孝贤监制 萧雅全导演作品\n国/闽南语中字",
            "5335600000000003",
            "2026-08-25",
        )
        assert info is not None
        assert info.supervisor == "侯孝贤"
        assert info.director == "萧雅全"
        assert info.awards == "台北电影奖最佳剧情长片提名作品"
        # “剧情长片”中的“剧情”不与显示形式“剧情片”重复，类别保留
        assert info.category == "剧情"
        filename = info.generate_filename()
        assert "侯孝贤监制 萧雅全导演 台北电影奖最佳剧情长片提名作品 剧情片 国闽南语中字" in filename

    def test_category_kept_when_award_has_feature_length_variant(self, extractor):
        # 回归对照：奖项含“剧情片/剧情短片”（即显示形式）时类别抑制（曼克/讲话没有在听）
        info = extractor.extract(
            "《曼克》\n大卫·芬奇导演作品\n金球奖最佳剧情片提名作品\n英语中英双字",
            "5335600000000004",
            "2026-08-21",
        )
        assert info is not None
        assert info.category is None
        info2 = extractor.extract(
            "《讲话没有在听》\n金马最佳剧情短片获奖作品\n国闽南语中英双字",
            "5335600000000005",
            "2026-08-21",
        )
        assert info2 is not None
        assert info2.category is None
        # 奖项含“动画长片”且“动画”即类型词本身 → 类别抑制（妮莫娜）
        info3 = extractor.extract(
            "《怪物少女妮莫娜》\n奥斯卡金像奖最佳动画长片提名作品\n英语中英双字",
            "5335600000000006",
            "2026-08-22",
        )
        assert info3 is not None
        assert info3.category is None

    def test_extract_cannes_dual_award_and_flemish_language(self, extractor):
        # 回归：戛纳金摄影机奖、酷儿棕榈奖并列 + 法/弗拉芒/英语（女孩）
        info = extractor.extract(
            "《女孩》\n戛纳电影节金摄影机奖、酷儿棕榈奖获奖作品\n卢卡斯·德霍特导演高分作品\n法/弗拉芒/英语中字",
            "5335600000000007",
            "2026-08-25",
        )
        assert info is not None
        assert info.awards == "戛纳电影节金摄影机奖、酷儿棕榈奖获奖作品"
        assert info.language == "法弗拉芒英语"
        filename = info.generate_filename()
        assert "戛纳电影节金摄影机奖、酷儿棕榈奖获奖作品 高分片 法弗拉芒英语中字" in filename

    def test_extract_german_english_french_slash_language(self, extractor):
        # 回归：德/英/法语 → 德英法语（美国朋友）
        info = extractor.extract(
            "《美国朋友》\n维姆·文德斯导演作品\n德/英/法语中英双字",
            "5335600000000008",
            "2026-08-25",
        )
        assert info is not None
        assert info.language == "德英法语"
        assert info.subtitle == "中英双字"

    def test_concert_film_title_with_anniversary_not_skipped(self, extractor):
        # 回归：片名含“周年”（《悲惨世界:十周年纪念演唱会》）不算非影视内容
        text = "《悲惨世界:十周年纪念演唱会》\n热门高分音乐剧现场推荐\n英语中英双字"
        assert extractor.is_non_movie_content(text) is False
        info = extractor.extract(text, "5335600000000009", "2026-08-25")
        assert info is not None
        assert info.chinese_name == "悲惨世界：十周年纪念演唱会"
        # “周年”在书名号外仍触发跳过（周年纪念贴）
        assert extractor.is_non_movie_content("《教父》上映五十周年纪念") is True
