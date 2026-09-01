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

    def test_extract_silent_animation_genre(self, extractor):
        # 回归：无对白+动画 连写作为整体类型词；类别被“最佳动画长片”抑制后
        # “无对白”前缀类型仍显示（男孩与世界）
        info = extractor.extract(
            "《男孩与世界》\n奥斯卡金像奖最佳动画长片提名作品\n无对白动画\n见平👇",
            "5335700000000001",
            "2026-08-26",
        )
        assert info is not None
        assert info.genre == "无对白动画"
        assert info.category is None
        filename = info.generate_filename()
        assert "奥斯卡金像奖最佳动画长片提名作品 无对白动画" in filename

    def test_extract_cannes_directors_fortnight_award(self, extractor):
        # 回归：戛纳电影节导演双周单元提名作品；A24出品 独立段置于获奖之后（男人）
        info = extractor.extract(
            "《男人》\n杰西·巴克利主演 亚历克斯·加兰导演作品\n"
            "戛纳电影节导演双周单元提名作品\nA24出品恐怖电影\n英语中英双字",
            "5335700000000002",
            "2026-08-26",
        )
        assert info is not None
        assert info.awards == "戛纳电影节导演双周单元提名作品"
        assert info.producer_tag == "A24出品"
        filename = info.generate_filename()
        assert "戛纳电影节导演双周单元提名作品 A24出品 恐怖片" in filename

    def test_extract_japanese_mandarin_slash_language(self, extractor):
        # 回归：日/国语 → 日国语（漂泊皇妃）
        info = extractor.extract(
            "《漂泊皇妃》\n田中绢代执导 京町子主演电影\n日/国语中字",
            "5335700000000003",
            "2026-08-26",
        )
        assert info is not None
        assert info.language == "日国语"
        assert info.subtitle == "中字"
        filename = info.generate_filename()
        assert "日国语中字" in filename

    def test_extract_version_credit(self, extractor):
        # 回归：“X版”演员版本署名独立成段，置于改编/获奖之后（伊豆的舞女）
        info = extractor.extract(
            "《伊豆的舞女》\n改编自川端康成同名原著\n鳄渊晴子版 日语中字",
            "5335700000000004",
            "2026-08-26",
        )
        assert info is not None
        assert info.version_credit == "鳄渊晴子版"
        filename = info.generate_filename()
        assert "改编自川端康成同名原著 鳄渊晴子版 日语中字" in filename
        # 通用版本词不作版本署名
        for raw in (
            "《海贼王(真人版）》\n热门高分奇幻动作剧集推荐",
            "《例片》\n修复版 高清电影推荐",
            "《例片》\n2024版 悬疑剧集推荐",
        ):
            other = extractor.extract(raw, "5335700000000099", "2026-08-26")
            assert other is not None
            assert other.version_credit is None

    def test_extract_variety_show_qi_episodes_and_slash_title(self, extractor):
        # 回归：综艺类型 + “全13期”期数段；片名自带的“/”保留（19/20 成年初体验）
        info = extractor.extract(
            "《19/20 成年初体验》\n冷门高分综艺推荐\n全13期 韩语中字",
            "5335700000000005",
            "2026-08-26",
        )
        assert info is not None
        assert info.chinese_name == "19/20 成年初体验"
        assert info.genre == "综艺"
        assert info.season_extra == "全13期"
        filename = info.generate_filename()
        assert filename.startswith("19/20 成年初体验")
        assert "冷门高分综艺 全13期 韩语中字" in filename

    def test_extract_berlin_silver_bear_jury_award(self, extractor):
        # 回归：柏林电影节银熊奖评审团奖获奖作品（百万美元酒店）
        info = extractor.extract(
            "《百万美元酒店》\n米拉·乔沃维奇/梅尔·吉布森主演电影\n"
            "柏林电影节银熊奖评审团奖获奖作品\n维姆·文德斯导演作品\n英语中字",
            "5335700000000006",
            "2026-08-26",
        )
        assert info is not None
        assert info.awards == "柏林电影节银熊奖评审团奖获奖作品"
        assert info.director == "维姆·文德斯"
        filename = info.generate_filename()
        assert "柏林电影节银熊奖评审团奖获奖作品" in filename

    def test_douban_foreign_name_embedded_in_chinese_dropped(self):
        # 回归：豆瓣外文名已包含在中文名里时不再追加（19/20 成年初体验）
        from douban import _drop_embedded_name

        assert _drop_embedded_name("19/20 成年初体验", "19/20") is None
        assert _drop_embedded_name("新飞越比佛利", "90210") == "90210"
        assert _drop_embedded_name("男孩与世界", None) is None

    def test_extract_ny_film_critics_best_picture_award(self, extractor):
        # 回归：纽约影评人协会奖最佳影片提名作品 → “协会奖”不保留“奖”字（孽扣）
        info = extractor.extract(
            "《孽扣》\n杰瑞米·艾恩斯主演 大卫·柯南伯格导演作品\n"
            "纽约影评人协会奖最佳影片提名作品\n英语中英双字",
            "5335800000000001",
            "2026-08-27",
        )
        assert info is not None
        assert info.awards == "纽约影评人协会最佳影片提名作品"
        assert info.director == "大卫·柯南伯格"
        filename = info.generate_filename()
        assert "纽约影评人协会最佳影片提名作品" in filename

    def test_extract_hk_film_awards_best_actress_award(self, extractor):
        # 回归：香港电影金像奖最佳女主角提名作品（填词L）
        info = extractor.extract(
            "《填词L》\n香港电影金像奖最佳女主角提名作品\n钟雪莹主演电影\n粤语中字",
            "5335800000000002",
            "2026-08-27",
        )
        assert info is not None
        assert info.awards == "香港电影金像奖最佳女主角提名作品"
        assert info.cast == ["钟雪莹"]
        filename = info.generate_filename()
        assert "钟雪莹主演 香港电影金像奖最佳女主角提名作品 粤语中字" in filename

    def test_extract_san_sebastian_audience_award(self, extractor):
        # 回归：圣塞巴斯蒂安电影节观众选择奖获奖作品（春夏秋冬又一春）；
        # “观众选择奖获奖”中的“奖”不适用最佳X去重规则，原样保留
        info = extractor.extract(
            "《春夏秋冬又一春》\n圣塞巴斯蒂安电影节观众选择奖获奖作品\n金基德导演高分作品\n韩语中字",
            "5335800000000003",
            "2026-08-27",
        )
        assert info is not None
        assert info.awards == "圣塞巴斯蒂安电影节观众选择奖获奖作品"
        filename = info.generate_filename()
        assert "金基德导演 圣塞巴斯蒂安电影节观众选择奖获奖作品 高分片" in filename

    def test_extract_cesar_best_actor_award(self, extractor):
        # 回归：法国凯撒电影奖最佳男主角获奖作品，奖项名内层“奖”按惯例去掉（伊夫·圣罗兰传）
        info = extractor.extract(
            "《伊夫·圣罗兰传》\n法国凯撒电影奖最佳男主角获奖作品\n皮埃尔·尼内主演传记电影\n法语中法双字",
            "5335800000000004",
            "2026-08-27",
        )
        assert info is not None
        assert info.awards == "法国凯撒电影奖最佳男主角获奖作品"
        assert info.category == "传记"
        filename = info.generate_filename()
        assert "法国凯撒电影奖最佳男主角获奖作品 传记片" in filename

    def test_extract_european_film_award_and_spanish_latin_language(self, extractor):
        # 回归：欧洲电影奖最佳影片提名作品 + 西/拉丁语 → 西拉丁语（不良教育）
        info = extractor.extract(
            "《不良教育》\n欧洲电影奖最佳影片提名作品\n佩德罗·阿莫多瓦导演作品\n西/拉丁语中字",
            "5335800000000005",
            "2026-08-27",
        )
        assert info is not None
        assert info.awards == "欧洲电影奖最佳影片提名作品"
        assert info.language == "西拉丁语"
        assert info.subtitle == "中字"
        filename = info.generate_filename()
        assert "欧洲电影奖最佳影片提名作品 西拉丁语中字" in filename

    def test_extract_tongxing_category(self, extractor):
        # 回归：同性作为类别词（军靴男孩，热门高分喜剧同性剧集）
        info = extractor.extract(
            "《军靴男孩》\n热门高分喜剧同性剧集推荐\n全8集 英语中英双字\n见平👇",
            "5335800000000010",
            "2026-08-28",
        )
        assert info is not None
        assert info.category == "喜剧/同性"
        filename = info.generate_filename()
        assert "热门高分喜剧同性剧集 全8集" in filename

    def test_extract_tiyu_category(self, extractor):
        # 回归：体育作为类别词（传奇之师：新英格兰爱国者，冷门高分体育纪录剧集）
        info = extractor.extract(
            "《传奇之师：新英格兰爱国者》\n冷门高分体育纪录剧集推荐\n全10集 英语中字\n见平👇",
            "5335800000000011",
            "2026-08-28",
        )
        assert info is not None
        assert info.category == "体育/纪录"
        filename = info.generate_filename()
        assert "冷门高分体育纪录剧集 全10集" in filename

    def test_extract_teddy_best_film_award(self, extractor):
        # 回归：柏林电影节泰迪熊奖最佳电影提名作品完整保留（荧屏在发光）
        info = extractor.extract(
            "《荧屏在发光》\n柏林电影节泰迪熊奖最佳电影提名作品\n简·申布伦执导恐怖电影\n英语中英双字\n见平👇",
            "5335800000000012",
            "2026-08-28",
        )
        assert info is not None
        assert info.awards == "柏林电影节泰迪熊奖最佳电影提名作品"
        filename = info.generate_filename()
        assert "柏林电影节泰迪熊奖最佳电影提名作品 恐怖片" in filename

    def test_extract_cannes_main_competition_best_screenplay_award(self, extractor):
        # 回归：戛纳电影节主竞赛单元最佳编剧获奖作品（圣鹿之死），
        # 单元名与提名/获奖之间的“最佳XX”此前不被识别导致奖项丢失
        info = extractor.extract(
            "《圣鹿之死》\n妮可·基德曼/科林·法瑞尔主演悬疑惊悚片\n戛纳电影节主竞赛单元最佳编剧获奖作品\n英语中英双字\n见平👇",
            "5335800000000013",
            "2026-08-28",
        )
        assert info is not None
        assert info.awards == "戛纳电影节主竞赛单元最佳编剧获奖作品"
        filename = info.generate_filename()
        assert "戛纳电影节主竞赛单元最佳编剧获奖作品 悬疑惊悚片" in filename

    def test_extract_golden_horse_original_screenplay_award(self, extractor):
        # 回归：金马最佳原著剧本提名作品（该死的阿修罗），金马官方名为“原著剧本”
        info = extractor.extract(
            "《该死的阿修罗》\n金马最佳原著剧本提名作品\n国/闽南语中字\n见平👇",
            "5335800000000014",
            "2026-08-28",
        )
        assert info is not None
        assert info.awards == "金马最佳原著剧本提名作品"
        filename = info.generate_filename()
        assert "金马最佳原著剧本提名作品 国闽南语中字" in filename

    def test_award_trailing_genre_stripped_and_genre_shown(self, extractor):
        # 回归：圣丹斯电影节展映纪录片（权力背后）——奖项末尾“纪录片”剥离进 genre
        # 后独立显示，与“洛迦诺电影节展映 纪录片”先例一致
        info = extractor.extract(
            "《权力背后》\n圣丹斯电影节展映纪录片\n英语中字\n见平👇",
            "5335800000000015",
            "2026-08-28",
        )
        assert info is not None
        assert info.genre == "纪录片"
        filename = info.generate_filename()
        assert "圣丹斯电影节展映 纪录片" in filename

    def test_extract_included_season_with_language(self, extractor):
        # 回归：“含中英双字第一季”（人生复本）——语言已单独提取，改写为“含第一季”
        info = extractor.extract(
            "《人生复本》\n乔尔·埃哲顿/詹妮弗·康纳利主演科幻剧集\n第二季首播至第一集\n含中英双字第一季\n见平👇",
            "5335800000000016",
            "2026-08-28",
        )
        assert info is not None
        assert info.season_extra == "第二季首播至第一集 含第一季"
        assert info.subtitle == "中英双字"
        filename = info.generate_filename()
        assert "第二季首播至第一集 含第一季 中英双字" in filename

    def test_extract_included_zhongzi_season_kept_verbatim(self, extractor):
        # 回归：“含中字第一季”（女警出更）惯用语原样保留，不被语言剥离规则改写
        info = extractor.extract(
            "《女警出更》\n悬疑犯罪剧集\n第二季首播至第一集\n含中字第一季\n中字\n见平👇",
            "5335800000000017",
            "2026-08-28",
        )
        assert info is not None
        assert info.season_extra == "第二季首播至第一集 含中字第一季"
        filename = info.generate_filename()
        assert "第二季首播至第一集 含中字第一季" in filename

    def test_extract_venice_fipresci_award(self, extractor):
        # 回归：威尼斯电影节费比西奖获奖作品（厚望）
        info = extractor.extract(
            "《厚望》\n威尼斯电影节费比西奖获奖作品\n迈克·李导演作品\n英语中字\n见平👇",
            "5335800000000018",
            "2026-08-29",
        )
        assert info is not None
        assert info.awards == "威尼斯电影节费比西奖获奖作品"
        filename = info.generate_filename()
        assert "威尼斯电影节费比西奖获奖作品" in filename

    def test_extract_adapted_from_narrative_poem(self, extractor):
        # 回归：改编自同名叙事诗（午宴之歌）——改编尾词交替项含“叙事诗”
        info = extractor.extract(
            "《午宴之歌》\n艾玛·汤普森/艾伦·瑞克曼主演电影\n改编自同名叙事诗\n英语中英双字\n见平👇",
            "5335800000000019",
            "2026-08-29",
        )
        assert info is not None
        assert info.awards == "改编自同名叙事诗"
        filename = info.generate_filename()
        assert "（改编自同名叙事诗 艾玛·汤普森、艾伦·瑞克曼主演" in filename

    def test_extract_gotham_award(self, extractor):
        # 回归：哥谭独立电影奖最佳纪录片提名作品（波士顿市政厅）——官方名无“节”，照抄原文
        info = extractor.extract(
            "《波士顿市政厅》\n哥谭独立电影奖最佳纪录片提名作品\n弗雷德里克·怀斯曼导演作品\n英语中英双字\n见平👇",
            "5335800000000020",
            "2026-08-29",
        )
        assert info is not None
        assert info.awards == "哥谭独立电影奖最佳纪录片提名作品"
        # 奖项中已含“纪录”，genre“纪录片”按惯例不重复显示
        filename = info.generate_filename()
        assert "哥谭独立电影奖最佳纪录片提名作品 英语中英双字" in filename

    def test_extract_bucheon_netpac_and_golden_horse_cinematography(self, extractor):
        # 回归：富川奇幻电影节亚洲电影促进联盟大奖 + 金马最佳摄影双奖项（青春并不温柔）
        # 按原文顺序输出；奖项行中的“奇幻”不再误入类别
        info = extractor.extract(
            "《青春并不温柔》\n富川奇幻电影节亚洲电影促进联盟大奖获奖作品\n金马最佳摄影提名作品\n国语中英双字\n见平👇",
            "5335800000000021",
            "2026-08-29",
        )
        assert info is not None
        assert info.awards == "富川奇幻电影节亚洲电影促进联盟大奖获奖作品 金马最佳摄影提名作品"
        assert info.category is None
        filename = info.generate_filename()
        assert "（富川奇幻电影节亚洲电影促进联盟大奖获奖作品 金马最佳摄影提名作品" in filename

    def test_extract_rotterdam_tiger_award(self, extractor):
        # 回归：鹿特丹电影节老虎奖最佳影片提名作品（麻木）
        info = extractor.extract(
            "《麻木》\n鹿特丹电影节老虎奖最佳影片提名作品\n波斯语中字\n见平👇",
            "5335800000000022",
            "2026-08-30",
        )
        assert info is not None
        assert info.awards == "鹿特丹电影节老虎奖最佳影片提名作品"
        filename = info.generate_filename()
        assert "鹿特丹电影节老虎奖最佳影片提名作品" in filename

    def test_extract_cannes_jury_grand_prize_without_zuijia(self, extractor):
        # 回归：戛纳主竞赛单元评审团大奖（母亲与娼妓）——“评审团大奖”可不带“最佳”前缀
        info = extractor.extract(
            "《母亲与娼妓》\n让·厄斯塔什执导 让-皮埃尔·利奥德主演电影\n戛纳电影节主竞赛单元评审团大奖获奖作品\n法语中字\n见平👇",
            "5335800000000023",
            "2026-08-30",
        )
        assert info is not None
        assert info.awards == "戛纳电影节主竞赛单元评审团大奖获奖作品"
        assert info.director == "让·厄斯塔什"
        filename = info.generate_filename()
        assert "戛纳电影节主竞赛单元评审团大奖获奖作品" in filename

    def test_extract_venice_orizzonti_award(self, extractor):
        # 回归：威尼斯电影节地平线单元奖最佳影片提名作品（愚行录）
        info = extractor.extract(
            "《愚行录》\n威尼斯电影节地平线单元奖最佳影片提名作品\n妻夫木聪/满岛光主演电影\n日语中字\n见平👇",
            "5335800000000024",
            "2026-08-30",
        )
        assert info is not None
        assert info.awards == "威尼斯电影节地平线单元奖最佳影片提名作品"
        filename = info.generate_filename()
        assert "威尼斯电影节地平线单元奖最佳影片提名作品" in filename

    def test_slash_language_combo_verbatim(self, extractor):
        # 回归：斜杠组合语言照抄原文去斜杠（一千次晚安 挪威/英语、冲突 英/西/意语），
        # 不把“挪威”补成“挪威语”、“英”补成“英语”（与 SLASH_REPLACEMENTS 表风格一致）
        info = extractor.extract(
            "《一千次晚安》\n朱丽叶·比诺什主演电影\n挪威/英语中英双字\n见平👇",
            "5335800000000025",
            "2026-08-30",
        )
        assert info is not None
        assert info.language == "挪威英语"
        assert info.subtitle == "中英双字"

        info2 = extractor.extract(
            "《冲突》\n阿尔·帕西诺主演 西德尼·吕美特导演作品\n英/西/意语中英双字\n见平👇",
            "5335800000000026",
            "2026-08-30",
        )
        assert info2 is not None
        assert info2.language == "英西意语"
        assert info2.subtitle == "中英双字"

    def test_slash_language_indi_english_frozen_spelling(self, extractor):
        # 回归：铁道人“印地/英语”历史拼法为“印地语英语”，按 08-16 基准冻结在表中
        info = extractor.extract(
            "《铁道人》\n高分惊悚历史剧集\n全4集 印地/英语中字\n见平👇",
            "5335800000000027",
            "2026-08-16",
        )
        assert info is not None
        assert info.language == "印地语英语"

    def test_extract_director_with_genre_word_before_type(self, extractor):
        # 回归：“三宅唱导演恐怖剧集作品”（咒怨：诅咒之家）——
        # 导演与“剧集作品”之间可夹类型词，人名照常提取
        info = extractor.extract(
            "《咒怨:诅咒之家》\n三宅唱导演恐怖剧集作品\n全6集 日语中字\n见平👇",
            "5335800000000028",
            "2026-08-30",
        )
        assert info is not None
        assert info.director == "三宅唱"
        assert info.category == "恐怖"
        assert info.genre == "剧集"
        filename = info.generate_filename()
        assert "三宅唱导演 恐怖剧集 全6集" in filename

    def test_extract_documentary_short_combined_genre(self, extractor):
        # 回归：“高分纪录短片”（房屋是黑的）——纪录短片整体作为组合类型词
        info = extractor.extract(
            "《房屋是黑的》\n芙茹弗·法洛克扎德执导高分纪录短片\n波斯语中字\n见平👇",
            "5335800000000029",
            "2026-08-30",
        )
        assert info is not None
        assert info.genre == "纪录短片"
        # 类别“短片/纪录”与 genre 互含，生成文件名时整体过滤，仅显示组合类型词
        filename = info.generate_filename()
        assert "高分纪录短片" in filename

    def test_goya_best_spanish_foreign_film(self, extractor):
        # 回归：烈焰焚币“西班牙戈雅奖最佳西班牙语外国片获奖作品”（09-01 基准）
        info = extractor.extract(
            "《烈焰焚币》\n莱昂纳多·斯巴拉格利亚主演\n西班牙戈雅奖最佳西班牙语外国片获奖作品\n西班牙语中字\n见平👇",
            "5335800000031",
            "2026-08-31",
        )
        assert info is not None
        assert info.awards == "西班牙戈雅奖最佳西班牙语外国片获奖作品"

    def test_golden_globe_limited_series_tv_movie(self, extractor):
        # 回归：迷恋荷尔蒙“金球奖最佳限定剧/电视电影提名作品”（09-01 基准）——
        # 原文半角斜杠，文件名中全角化（与夸克重命名后的目录名一致）
        info = extractor.extract(
            "《迷恋荷尔蒙》\n金球奖最佳限定剧/电视电影提名作品\n李·佩斯主演高分爱情犯罪电影\n英语中英双字\n见平👇",
            "5335800000032",
            "2026-08-31",
        )
        assert info is not None
        assert info.awards == "金球奖最佳限定剧/电视电影提名作品"
        assert "金球奖最佳限定剧／电视电影提名作品" in info.generate_filename()

    def test_tribeca_festival_screened_work(self, extractor):
        # 回归：静音重生“翠贝卡电影节展映电影作品”（09-01 基准）
        info = extractor.extract(
            "《静音重生》\n翠贝卡电影节展映电影作品\n已出英/法语中字\n见平👇",
            "5335800000033",
            "2026-08-31",
        )
        assert info is not None
        assert info.awards == "翠贝卡电影节展映电影作品"

    def test_afi_annual_best_films(self, extractor):
        # 回归：她说“美国电影学会奖年度佳片获奖作品”（09-01 基准）
        info = extractor.extract(
            "《她说》\n美国电影学会奖年度佳片获奖作品\n英语中英双字\n见平👇",
            "5335800000034",
            "2026-08-31",
        )
        assert info is not None
        assert info.awards == "美国电影学会奖年度佳片获奖作品"

    def test_trilogy_credit_after_oscar(self, extractor):
        # 回归：凯尔经的秘密““爱尔兰民俗三部曲”之一”（09-01 基准）——
        # 描述性系列荣誉，排在奥斯卡奖项之后
        info = extractor.extract(
            "《凯尔经的秘密》\n奥斯卡金像奖最佳动画长片提名作品\n“爱尔兰民俗三部曲”之一\n英语中英双字\n见平👇",
            "5335800000035",
            "2026-08-31",
        )
        assert info is not None
        assert "奥斯卡金像奖最佳动画长片提名作品" in info.awards
        assert "“爱尔兰民俗三部曲”之一" in info.awards
        filename = info.generate_filename()
        assert "奥斯卡金像奖最佳动画长片提名作品 “爱尔兰民俗三部曲”之一" in filename

    def test_slash_language_indonesian_english(self, extractor):
        # 回归：杀戮演绎“印尼/英语中英双字”→ 印尼英语（09-01 基准，印尼语入表）
        info = extractor.extract(
            "《杀戮演绎》\n奥斯卡金像奖最佳纪录长片提名作品\n印尼/英语中英双字\n见平👇",
            "5335800000036",
            "2026-08-31",
        )
        assert info is not None
        assert info.language == "印尼英语"
        assert info.subtitle == "中英双字"

    def test_yichu_prefix_stripped_from_language(self, extractor):
        # 回归：静音重生“已出英/法语中字”——“已出”是状态词，不属于语言名
        info = extractor.extract(
            "《静音重生》\n翠贝卡电影节展映电影作品\n已出英/法语中字\n见平👇",
            "5335800000037",
            "2026-08-31",
        )
        assert info is not None
        assert info.language == "英法语"
        assert info.subtitle == "中字"

    def test_yichu_prefix_stripped_single_language(self, extractor):
        # “已出日语中字”同样剥离“已出”（推理竞技场形态）
        info = extractor.extract(
            "《推理竞技场》\n冷门高分电影推荐\n已出日语中字\n见平👇",
            "5335800000038",
            "2026-08-15",
        )
        assert info is not None
        assert info.language == "日语"
        assert info.subtitle == "中字"

    def test_genre_word_plus_ju_is_series(self, extractor):
        # 回归：伴人而生“主演悬疑剧”+“全12集”——“类型+剧”连写视作剧集
        info = extractor.extract(
            "《伴人而生》\n水上恒司/山田杏奈主演悬疑剧\n全12集 日语中日双字\n见平👇",
            "5335800000039",
            "2026-08-31",
        )
        assert info is not None
        assert info.genre == "剧集"
        assert info.category == "悬疑"
        filename = info.generate_filename()
        assert "悬疑剧集 全12集" in filename

    def test_musical_stays_movie_not_series(self, extractor):
        # 回归：玛蒂尔达“高分喜剧歌舞片推荐”——音乐剧/歌舞剧是电影类型，
        # 不得因“类型+剧”规则误判为剧集
        info = extractor.extract(
            "《玛蒂尔达:音乐剧》\n高分喜剧歌舞片推荐\n英语中字\n见平👇",
            "5335800000040",
            "2026-08-22",
        )
        assert info is not None
        assert info.genre == "电影"

    def test_musical_stage_rec_stays_movie(self, extractor):
        # 回归：悲惨世界“热门高分音乐剧现场推荐”——剧场现场音乐剧电影
        info = extractor.extract(
            "《悲惨世界:十周年纪念演唱会》\n热门高分音乐剧现场推荐\n英语中字\n见平👇",
            "5335800000041",
            "2026-08-25",
        )
        assert info is not None
        assert info.genre == "电影"

    def test_genre_plus_ju_blocked_by_following_words(self, extractor):
        # “类型+剧”后接 情/场/照/本 时不判剧集（喜剧剧情片、美食剧场版等）
        info = extractor.extract(
            "《测试片》\n高分喜剧剧情片推荐\n英语中字\n见平👇",
            "5335800000042",
            "2026-08-31",
        )
        assert info is not None
        assert info.genre == "电影"

    def test_family_genre_category(self, extractor):
        # 回归：全家变身大作战“主演喜剧家庭片”——“家庭”入类别表（09-02 基准）
        info = extractor.extract(
            "《全家变身大作战》\n詹妮弗·加纳/艾玛·迈尔斯主演喜剧家庭片\n英语中英双字\n见平👇",
            "5335800000051",
            "2026-09-01",
        )
        assert info is not None
        assert info.category == "喜剧/家庭"
        filename = info.generate_filename()
        assert "喜剧家庭片" in filename

    def test_rotterdam_audience_award(self, extractor):
        # 回归：罪人“鹿特丹电影节观众奖获奖作品”（09-02 基准）
        info = extractor.extract(
            "《罪人》\n鹿特丹电影节观众奖获奖作品\n热门惊悚犯罪电影推荐\n丹麦语中字\n见平👇",
            "5335800000052",
            "2026-09-01",
        )
        assert info is not None
        assert info.awards == "鹿特丹电影节观众奖获奖作品"

    def test_nbr_top10_indie_films_kept_whole(self, extractor):
        # 回归：松林外“美国国家评论协会奖十佳独立电影”——
        # “电影”是荣誉名一部分，不被泛型剥离（09-02 基准）
        info = extractor.extract(
            "《松林外》\n瑞恩·高斯林/布莱德利·库珀主演犯罪电影\n美国国家评论协会奖十佳独立电影\n英语中英双字\n见平👇",
            "5335800000053",
            "2026-09-01",
        )
        assert info is not None
        assert info.awards == "美国国家评论协会奖十佳独立电影"
        filename = info.generate_filename()
        assert "美国国家评论协会奖十佳独立电影 犯罪片" in filename

    def test_critics_choice_award_keeps_cast_category(self, extractor):
        # 回归：耐撕侦探“最佳喜剧片”与主演行“喜剧动作犯罪片”并存——
        # 奖项外的类别词保留，各表各的（09-02 基准）
        info = extractor.extract(
            "《耐撕侦探》\n罗素·克劳/瑞恩·高斯林主演喜剧动作犯罪片\n美国评论家选择奖最佳喜剧片提名作品\n英语中英双字\n见平👇",
            "5335800000054",
            "2026-09-01",
        )
        assert info is not None
        assert info.awards == "美国评论家选择奖最佳喜剧片提名作品"
        assert info.category == "喜剧/犯罪/动作"
        filename = info.generate_filename()
        assert "美国评论家选择奖最佳喜剧片提名作品 喜剧犯罪动作片" in filename

    def test_rating_shown_with_category_word_despite_adaptation(self, extractor):
        # 回归：异乡人“改编自…高分原著”+“主演高分传记片”——
        # 奖项内已有“高分”时，“高分+类型词”的独立用法仍显示评级（09-02 基准）
        info = extractor.extract(
            "《异乡人:上海的芥川龙之介》\n改编自芥川龙之介高分原著《上海游记》\n松田龙平主演高分传记片\n日语中日双字\n见平👇",
            "5335800000055",
            "2026-09-01",
        )
        assert info is not None
        assert info.rating == "高分"
        filename = info.generate_filename()
        assert "松田龙平主演 高分传记片" in filename

    def test_rating_hidden_when_only_gaofen_works(self, extractor):
        # 回归：我曾侍候过英国国王“导演高分作品”——奖项含“高分原著”时，
        # “高分作品”不是独立评级用法，不显示（09-01 基准维持）
        info = extractor.extract(
            "《我曾侍候过英国国王》\n改编自博胡米尔·赫拉巴尔同名高分原著\n柏林电影节金熊奖提名作品\n伊日·门泽尔导演高分作品\n多语中字\n见平👇",
            "5335800000056",
            "2026-08-31",
        )
        assert info is not None
        assert info.rating is None
        filename = info.generate_filename()
        assert "伊日·门泽尔导演 多语中字" in filename

    def test_rating_gaofen_works_shown_without_adaptation(self, extractor):
        # 回归对照：喜宴“李安导演高分作品”无改编文本时评级正常显示
        info = extractor.extract(
            "《喜宴》\n李安导演高分作品\n国语中字\n见平👇",
            "5335800000057",
            "2026-08-31",
        )
        assert info is not None
        assert info.rating == "高分"

    def test_rating_hidden_for_compound_word_in_adaptation(self, extractor):
        # 回归：龙纹身的女孩“改编自同名热门高分原著”——复合评级词
        # “热门高分”及其子词都属奖项文本，不作为评级（09-02 基准维持）
        info = extractor.extract(
            "《龙纹身的女孩》\n改编自同名热门高分原著\n鲁妮·玛拉/丹尼尔·克雷格主演\n大卫·芬奇导演作品\n悬疑惊悚电影\n英语中字\n见平👇",
            "5335800000058",
            "2026-08-27",
        )
        assert info is not None
        assert info.rating is None
        filename = info.generate_filename()
        assert "悬疑惊悚片" in filename
        assert "热门悬疑惊悚片" not in filename
