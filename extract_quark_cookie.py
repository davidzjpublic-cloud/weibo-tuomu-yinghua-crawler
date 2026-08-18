#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取浏览器中的夸克网盘登录 Cookie，并写入 config.json 的 quark_cookie 字段。

使用方法：
1. 在浏览器中登录 https://pan.quark.cn（确保是登录状态）
2. 关闭浏览器，避免 Cookie 数据库被锁定（Chrome/Edge 尤其重要）
3. 运行：python extract_quark_cookie.py
4. 脚本会自动把提取到的 Cookie 填入 config.json 的 quark_cookie 字段
"""

import json
import sys
from pathlib import Path

try:
    import browser_cookie3
except ImportError:
    print("请先安装依赖：pip install browser-cookie3")
    sys.exit(1)


# 脚本所在目录下的 config.json
CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

# 夸克相关域名，按优先级尝试
QUARK_DOMAINS = [
    "quark.cn",
    "pan.quark.cn",
    "drive-m.quark.cn",
    "drive.quark.cn",
    ".quark.cn",
]

# 关键登录态 Cookie（至少包含其中一部分才认为可能有效）
ESSENTIAL_COOKIE_NAMES = {"__pus", "__puus", "__kp", "__kps", "__kpe"}


def get_browser_functions():
    """获取可用的浏览器 Cookie 提取函数列表。"""
    candidates = [
        ("Chrome", "chrome"),
        ("Edge", "edge"),
        ("Firefox", "firefox"),
        ("Chromium", "chromium"),
        ("Opera", "opera"),
        ("Brave", "brave"),
    ]
    functions = []
    for label, attr in candidates:
        func = getattr(browser_cookie3, attr, None)
        if callable(func):
            functions.append((label, func))
    return functions


def extract_quark_cookies(browser_func):
    """从某个浏览器中提取夸克网盘相关 Cookie。"""
    cookies = {}
    errors = []
    for domain in QUARK_DOMAINS:
        try:
            cj = browser_func(domain_name=domain)
            for cookie in cj:
                # 只保留域名中包含 quark 的 Cookie
                if "quark" in cookie.domain:
                    if cookie.name not in cookies:
                        cookies[cookie.name] = cookie.value
        except Exception as e:
            # 单个域名失败继续尝试下一个，但记录错误便于排查
            errors.append(f"{domain}: {e}")
            continue
    return cookies, errors


def build_cookie_string(cookies: dict) -> str:
    """将 Cookie 字典拼接为 HTTP Cookie 请求头格式。"""
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def main():
    print("=" * 50)
    print("夸克网盘 Cookie 提取工具")
    print("=" * 50)

    browser_functions = get_browser_functions()
    if not browser_functions:
        print("未找到可用的浏览器提取接口，请检查 browser-cookie3 版本。")
        sys.exit(1)

    collected = {}
    for label, func in browser_functions:
        print(f"\n正在尝试 {label} ...")
        cookies, errors = extract_quark_cookies(func)
        if cookies:
            print(f"  ✓ 找到 {len(cookies)} 个夸克相关 Cookie")
            for name, value in cookies.items():
                if name not in collected:
                    collected[name] = value
        else:
            print(f"  - 未找到")
            if errors:
                print(f"  调试信息（最近一条）: {errors[-1]}")

    if not collected:
        print("\n未能从任何浏览器中提取到夸克 Cookie。请确认：")
        print("  1. 已在浏览器中登录 https://pan.quark.cn")
        print("  2. 运行本脚本前已关闭浏览器（避免 Cookie 数据库被锁定）")
        print("  3. 使用的是本机默认浏览器配置文件（非多用户/访客模式）")
        sys.exit(1)

    cookie_str = build_cookie_string(collected)
    print(f"\n提取到的 Cookie 名称: {', '.join(collected.keys())}")

    found_essential = ESSENTIAL_COOKIE_NAMES & set(collected.keys())
    if not found_essential:
        print("\n⚠ 警告：未找到关键的登录态 Cookie（__pus / __puus 等），")
        print("   提取结果可能无法用于夸克 API 转存。")
    else:
        print(f"\n✓ 包含关键登录态 Cookie: {', '.join(found_essential)}")

    # 读取现有 config.json
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"\n警告：{CONFIG_FILE} 解析失败，将重新创建: {e}")
            config = {}
        except Exception as e:
            print(f"\n读取 {CONFIG_FILE} 失败: {e}")
            sys.exit(1)

    old_length = len(config.get("quark_cookie", ""))
    config["quark_cookie"] = cookie_str

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已写入 {CONFIG_FILE}")
        print(f"   旧 Cookie 长度: {old_length}")
        print(f"   新 Cookie 长度: {len(cookie_str)}")
    except Exception as e:
        print(f"\n写入 {CONFIG_FILE} 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
