# 微博【拓木映画】爬虫

抓取微博用户 **拓木映画**（UID 7608233324）每日发布的影视资源博文，从正文和评论中的夸克网盘分享链接提取影片信息，结合豆瓣搜索补全外文名与评分，生成规范化的资源文件名，并可转存到夸克网盘并改名。

## 流程

1. **抓取微博**（`crawler.py`）：按 `--target-date` 抓取当日博文及评论，收集拓木映画发布的夸克分享链接
2. **解析夸克分享**（`quark.py`）：访问分享页，提取网盘内文件名（含电影名、年份、豆瓣评分等信息）
3. **提取影视信息**（`extractor.py`）：从微博正文中提取中文名、导演/编剧/主演、获奖、评级、类型、语言字幕、季集数等
4. **豆瓣补全**（`douban.py`）：按中文名（带年份消歧）搜索豆瓣，取外文名与评分
5. **生成文件名**（`models.py`）：输出形如
   `中文名 外文名 年份（主演 导演 获奖 评级类别 季集 语言字幕 豆瓣X.X）`
6. **（可选）转存**：`--save` 时将资源转存到夸克网盘 `来自：分享/【拓临】` 目录并以上述文件名改名

## 使用

```powershell
# 安装依赖
pip install -r requirements.txt

# 复制凭据模板并填入自己的 Cookie（微博 + 夸克）
copy config.json.example config.json

# 抓取昨天的微博（默认目标日期为昨天），输出 results_日期.json 与 filenames_日期.txt
python main.py

# 指定日期并转存夸克网盘
python main.py --target-date 2026-08-18 --save
```

## 主要参数

| 参数 | 说明 |
| --- | --- |
| `--target-date YYYY-MM-DD` | 抓取哪一天的博文，默认昨天；输出文件名中的日期以它为准 |
| `--save` | 转存资源到夸克网盘并按生成文件名改名 |
| `--skip-processed` | 跳过已处理过的微博（默认不跳过，重跑会覆盖） |

## 测试

```powershell
python -m pytest tests/ -q
```

## 安全说明

`config.json`（微博/夸克登录 Cookie）、`备忘.txt`（含 API Key）等敏感文件已通过 `.gitignore` 排除，不在仓库中。首次使用请按 `config.json.example` 填写自己的凭据。
