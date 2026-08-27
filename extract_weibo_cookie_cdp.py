#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Chrome DevTools Protocol (CDP) 提取微博登录 Cookie。

首次运行请在弹出的 Chrome 窗口中登录微博；登录成功后脚本自动提取
Cookie 并写入 config.json 的 weibo_cookie 字段。后续运行可直接提取。

使用方法：
    python extract_weibo_cookie_cdp.py
"""

import re
import time
from pathlib import Path

from cdp_utils import (
    build_cookie_string,
    get_all_cookies,
    get_requests_session,
    run_cdp_flow,
)

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"
PROFILE_DIR = Path(__file__).resolve().parent / "chrome_weibo_profile"
PORT = 9223
TARGET_URL = "https://weibo.com/login.php"
WEIBO_UID = "7608233324"

ESSENTIAL_COOKIE_NAMES = {"SUB", "SUBP"}
REQUIRED_LOGIN_COOKIES = {"SUB", "SUBP"}


def is_weibo_related_cookie(domain: str) -> bool:
    """判断 Cookie 域名是否属于微博登录体系。"""
    d = domain.lower().lstrip(".")
    return any(kw in d for kw in ("weibo", "sina", "sinaimg.cn", "sinajs.cn"))


def cookie_is_logged_in(cookie_str: str) -> bool:
    """实测 Cookie 是否为有效登录态（排除游客会话）。"""
    session = get_requests_session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://weibo.com",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie_str,
    }
    xsrf = re.search(r"XSRF-TOKEN=([^;]+)", cookie_str)
    if xsrf:
        headers["X-XSRF-TOKEN"] = xsrf.group(1)
    try:
        r = session.get(
            "https://weibo.com/ajax/statuses/mymblog",
            params={"uid": WEIBO_UID, "page": 1, "feature": 0},
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200 and r.json().get("ok") == 1:
            return True
        print(f"\n   Cookie 验证未通过: HTTP {r.status_code} {r.text[:60]}")
    except Exception as e:
        print(f"\n   Cookie 验证请求异常: {e}")
    return False


def wait_for_login(ws_url: str, timeout: int = 300) -> list:
    """轮询等待用户在弹出的 Chrome 窗口中完成微博登录。"""
    print("\n请在弹出的 Chrome 窗口中登录微博。")
    print("登录成功后脚本会自动继续；若已登录过，会直接提取。\n")

    deadline = time.time() + timeout
    validated = False
    while time.time() < deadline:
        all_cookies = get_all_cookies(ws_url)
        weibo_cookies = [
            c for c in all_cookies
            if is_weibo_related_cookie(c.get("domain", ""))
        ]
        names = {c["name"] for c in weibo_cookies}
        found_essential = ESSENTIAL_COOKIE_NAMES & names

        if REQUIRED_LOGIN_COOKIES.issubset(names):
            time.sleep(2)
            all_cookies = get_all_cookies(ws_url)
            weibo_cookies = [
                c for c in all_cookies
                if is_weibo_related_cookie(c.get("domain", ""))
            ]
            if cookie_is_logged_in(build_cookie_string(weibo_cookies)):
                print(f"\n检测到有效登录态 Cookie: {', '.join(REQUIRED_LOGIN_COOKIES)}")
                validated = True
                return weibo_cookies
            print("\n已有 SUB/SUBP 但为游客/过期状态，请在窗口中登录微博账号", end="\r")

        remaining = int(deadline - time.time())
        hint = f"已检测到: {', '.join(found_essential)}" if found_essential else "未检测到登录态"
        print(f"等待登录中... {hint} | 还剩 {remaining} 秒（按 Ctrl+C 取消）", end="\r")
        time.sleep(3)

    if not validated:
        print("\n\n等待超时，未检测到有效登录态 Cookie（游客态不算）。")
    return []


def main():
    run_cdp_flow(
        tool_name="微博 Cookie 提取工具 (CDP 版)",
        profile_dir=PROFILE_DIR,
        port=PORT,
        target_url=TARGET_URL,
        domain_hint="weibo",
        log_filename="chrome_weibo_cdp_debug.log",
        config_key="weibo_cookie",
        config_file=CONFIG_FILE,
        wait_for_login_fn=wait_for_login,
    )


if __name__ == "__main__":
    main()
