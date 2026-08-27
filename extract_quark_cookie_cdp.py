#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Chrome DevTools Protocol (CDP) 提取夸克网盘登录 Cookie。

首次运行请在弹出的 Chrome 窗口中登录夸克网盘；登录成功后脚本自动提取
Cookie 并写入 config.json 的 quark_cookie 字段。后续运行可直接提取。

使用方法：
    python extract_quark_cookie_cdp.py
"""

import time
from pathlib import Path

from cdp_utils import (
    build_cookie_string,
    get_all_cookies,
    run_cdp_flow,
)

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"
PROFILE_DIR = Path(__file__).resolve().parent / "chrome_quark_profile"
PORT = 9222
TARGET_URL = "https://pan.quark.cn"

ESSENTIAL_COOKIE_NAMES = {"__pus", "__puus", "__kp", "__kps", "__kpe"}
REQUIRED_LOGIN_COOKIES = {"__pus", "__puus", "__kp"}


def wait_for_login(ws_url: str, timeout: int = 300) -> list:
    """轮询等待用户在弹出的 Chrome 窗口中完成夸克登录。"""
    print("\n请在弹出的 Chrome 窗口中登录夸克网盘。")
    print("登录成功后脚本会自动继续；若已登录过，会直接提取。\n")

    deadline = time.time() + timeout
    while time.time() < deadline:
        all_cookies = get_all_cookies(ws_url)
        quark_cookies = [c for c in all_cookies if "quark" in c.get("domain", "")]
        names = {c["name"] for c in quark_cookies}
        found_essential = ESSENTIAL_COOKIE_NAMES & names

        if REQUIRED_LOGIN_COOKIES.issubset(names):
            time.sleep(2)
            all_cookies = get_all_cookies(ws_url)
            quark_cookies = [c for c in all_cookies if "quark" in c.get("domain", "")]
            print(f"\n检测到关键登录态 Cookie: {', '.join(REQUIRED_LOGIN_COOKIES)}")
            return quark_cookies

        remaining = int(deadline - time.time())
        hint = f"已检测到: {', '.join(found_essential)}" if found_essential else "未检测到登录态"
        print(f"等待登录中... {hint} | 还剩 {remaining} 秒（按 Ctrl+C 取消）", end="\r")
        time.sleep(3)

    print("\n\n等待超时，未检测到关键登录态 Cookie。")
    return []


def main():
    run_cdp_flow(
        tool_name="夸克网盘 Cookie 提取工具 (CDP 版)",
        profile_dir=PROFILE_DIR,
        port=PORT,
        target_url=TARGET_URL,
        domain_hint="quark",
        log_filename="chrome_cdp_debug.log",
        config_key="quark_cookie",
        config_file=CONFIG_FILE,
        wait_for_login_fn=wait_for_login,
    )


if __name__ == "__main__":
    main()
