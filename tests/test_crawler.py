# -*- coding: utf-8 -*-
"""微博爬虫模块单元测试。"""

from unittest.mock import MagicMock

from crawler import WeiboCrawler


def make_crawler():
    crawler = WeiboCrawler.from_config_file(uid="7608233324")
    crawler.session = MagicMock()
    return crawler


def make_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


class TestGetCommentsFlowFallback:
    """时间流无夸克链接时回退热门流（月色撩人漏抓事件）。"""

    def test_hot_flow_fallback_when_time_flow_empty(self):
        crawler = make_crawler()
        time_flow = make_response({"ok": 1, "data": [], "max_id": 0})
        hot_flow = make_response({
            "ok": 1,
            "data": [
                {"id": "1", "text": "htt删ps://pan.quar掉k.cn/s/5410a字4d124c4"},
            ],
            "max_id": 0,
        })
        crawler._safe_request = MagicMock(side_effect=[time_flow, hot_flow])

        comments = crawler.get_comments("5338317767840660")

        assert len(comments) == 1
        assert crawler._safe_request.call_count == 2
        # 第二次请求为热门流 flow=1
        assert crawler._safe_request.call_args_list[1][1]["params"]["flow"] == 1

    def test_no_fallback_when_time_flow_has_quark_link(self):
        crawler = make_crawler()
        time_flow = make_response({
            "ok": 1,
            "data": [
                {
                    "id": "1",
                    "text": "见平👇",
                    "url_struct": [
                        {"short_url": "", "long_url": "https://pan.quark.cn/s/abc123"},
                    ],
                },
            ],
            "max_id": 0,
        })
        crawler._safe_request = MagicMock(return_value=time_flow)

        comments = crawler.get_comments("5338317767840660")

        assert len(comments) == 1
        # 时间流已有结构化夸克链接，不再请求热门流
        assert crawler._safe_request.call_count == 1

    def test_hot_flow_merged_with_dedup(self):
        crawler = make_crawler()
        time_flow = make_response({
            "ok": 1,
            "data": [{"id": "1", "text": "谢谢分享"}],
            "max_id": 0,
        })
        hot_flow = make_response({
            "ok": 1,
            "data": [
                {"id": "1", "text": "谢谢分享"},
                {"id": "2", "text": "htt删ps://pan.quar掉k.cn/s/5410a字4d124c4"},
            ],
            "max_id": 0,
        })
        crawler._safe_request = MagicMock(side_effect=[time_flow, hot_flow])

        comments = crawler.get_comments("5338317767840660")

        assert len(comments) == 2
        assert comments[1]["id"] == "2"
