#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Chrome DevTools Protocol (CDP) 提取微博登录 Cookie。

背景：
- Chrome 127+ 启用 App-Bound Encryption，browser-cookie3 无法从外部解密 Cookie。
- Chrome 136+ 禁止对默认用户数据目录开启远程调试，且复制出来的配置文件会
  使用不同的加密密钥，导致原登录 Cookie 无法解密。

因此本脚本使用一个**独立的 Chrome 配置文件**（位于脚本同目录下的
chrome_weibo_profile）。首次运行时，请在弹出的 Chrome 窗口中登录微博；
登录成功后脚本会自动提取 Cookie 并写入 config.json 的 weibo_cookie 字段。
若该配置文件中仍有有效登录态，后续运行可直接提取，无需再次登录。

使用方法：
    python extract_weibo_cookie_cdp.py

首次使用需交互：在弹出的 Chrome 窗口中完成微博登录。
"""

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
import websocket


CONFIG_FILE = Path(__file__).resolve().parent / "config.json"
WEIBO_PROFILE_DIR = Path(__file__).resolve().parent / "chrome_weibo_profile"
REMOTE_DEBUGGING_PORT = 9223
WEIBO_URL = "https://weibo.com/login.php"

# 判断微博登录态的关键 Cookie（至少要有 SUB / SUBP）
ESSENTIAL_COOKIE_NAMES = {"SUB", "SUBP"}
REQUIRED_LOGIN_COOKIES = {"SUB", "SUBP"}

_requests_session = None


def get_requests_session():
    """获取一个不走系统代理的 requests Session。"""
    global _requests_session
    if _requests_session is None:
        _requests_session = requests.Session()
        _requests_session.trust_env = False
    return _requests_session


def find_chrome_exe() -> str:
    """查找本机 chrome.exe 路径。"""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    chrome = shutil.which("chrome.exe")
    if chrome:
        return chrome
    return None


def hide_chrome_window(pid: int) -> None:
    """把属于指定进程 ID 的 Chrome 窗口隐藏掉。"""
    try:
        user32 = ctypes.windll.user32
        SW_HIDE = 0

        def callback(hwnd, _extra):
            if not user32.IsWindowVisible(hwnd):
                return True
            proc_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == pid:
                user32.ShowWindow(hwnd, SW_HIDE)
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
        )
        user32.EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        pass


def launch_chrome(log_path: Path = None) -> subprocess.Popen:
    """启动带远程调试端口的 Chrome，使用独立的微博爬虫配置目录。"""
    chrome = find_chrome_exe()
    if not chrome:
        print("未找到 chrome.exe，请确认 Google Chrome 已安装。")
        return None

    WEIBO_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome,
        f"--remote-debugging-port={REMOTE_DEBUGGING_PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir={WEIBO_PROFILE_DIR}",
        "--profile-directory=Default",
        "--no-first-run",
        "--no-default-browser-check",
        WEIBO_URL,
    ]
    print(f"正在启动 Chrome: {chrome}")
    print(f"独立配置目录: {WEIBO_PROFILE_DIR}")
    if log_path:
        print(f"启动日志: {log_path}")
        log_fp = open(log_path, "w", encoding="utf-8", errors="ignore")
    else:
        log_fp = open(os.devnull, "w")

    proc = subprocess.Popen(
        cmd,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        close_fds=True,
    )
    proc._log_fp = log_fp
    return proc


def wait_for_cdp(timeout: int = 30) -> bool:
    """等待 Chrome DevTools Protocol 可用。"""
    url = f"http://127.0.0.1:{REMOTE_DEBUGGING_PORT}/json/version"
    session = get_requests_session()
    for _ in range(timeout):
        try:
            r = session.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def get_page_ws_url() -> str:
    """获取一个可用页面的 WebSocket 调试地址。"""
    list_url = f"http://127.0.0.1:{REMOTE_DEBUGGING_PORT}/json/list"
    session = get_requests_session()
    r = session.get(list_url, timeout=10)
    r.raise_for_status()
    pages = r.json()

    for page in pages:
        if page.get("type") == "page" and "weibo" in (page.get("url") or ""):
            return page.get("webSocketDebuggerUrl")
    for page in pages:
        if page.get("type") == "page":
            return page.get("webSocketDebuggerUrl")

    new_url = f"http://127.0.0.1:{REMOTE_DEBUGGING_PORT}/json/new?{WEIBO_URL}"
    r = session.put(new_url, timeout=10)
    r.raise_for_status()
    return r.json().get("webSocketDebuggerUrl")


def get_all_cookies(ws_url: str) -> list:
    """通过 CDP 获取浏览器全部 Cookie。"""
    ws = websocket.create_connection(ws_url, timeout=15)
    try:
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        time.sleep(0.3)
        while True:
            msg = ws.recv()
            data = json.loads(msg)
            if data.get("id") == 1:
                break

        ws.send(json.dumps({"id": 2, "method": "Network.getAllCookies"}))
        deadline = time.time() + 10
        while time.time() < deadline:
            msg = ws.recv()
            data = json.loads(msg)
            if data.get("id") == 2:
                return data.get("result", {}).get("cookies", [])
        return []
    finally:
        ws.close()


def is_weibo_related_cookie(domain: str) -> bool:
    """判断 Cookie 域名是否属于微博登录体系。"""
    d = domain.lower().lstrip(".")
    return any(
        kw in d
        for kw in ("weibo", "sina", "sinaimg.cn", "sinajs.cn")
    )


def wait_for_login(ws_url: str, timeout: int = 300) -> list:
    """轮询等待用户在弹出的 Chrome 窗口中完成登录。"""
    print("\n请在弹出的 Chrome 窗口中登录微博。")
    print("登录成功后脚本会自动继续；若已登录过，会直接提取。\n")

    deadline = time.time() + timeout
    while time.time() < deadline:
        all_cookies = get_all_cookies(ws_url)
        weibo_cookies = [
            c for c in all_cookies
            if is_weibo_related_cookie(c.get("domain", ""))
        ]
        names = {c["name"] for c in weibo_cookies}
        found_essential = ESSENTIAL_COOKIE_NAMES & names
        if REQUIRED_LOGIN_COOKIES.issubset(names):
            # 稍等片刻，让可能延迟设置的 Cookie 也写入
            time.sleep(2)
            all_cookies = get_all_cookies(ws_url)
            weibo_cookies = [
                c for c in all_cookies
                if is_weibo_related_cookie(c.get("domain", ""))
            ]
            print(f"\n检测到关键登录态 Cookie: {', '.join(REQUIRED_LOGIN_COOKIES)}")
            return weibo_cookies

        remaining = int(deadline - time.time())
        hint = f"已检测到: {', '.join(found_essential)}" if found_essential else "未检测到登录态"
        print(f"等待登录中... {hint} | 还剩 {remaining} 秒（按 Ctrl+C 取消）", end="\r")
        time.sleep(3)

    print("\n\n等待超时，未检测到关键登录态 Cookie。")
    return []


def build_cookie_string(cookies: list) -> str:
    """将 CDP 返回的 Cookie 列表拼接为 HTTP Cookie 字符串。"""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def write_config(cookie_str: str) -> None:
    """将 Cookie 字符串写入 config.json，并保留一份备份。"""
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"警告：{CONFIG_FILE} 解析失败，将重新创建: {e}")
            config = {}
        except Exception as e:
            print(f"读取 {CONFIG_FILE} 失败: {e}")
            raise

    old_cookie = config.get("weibo_cookie", "")
    old_length = len(old_cookie)

    if old_cookie and old_cookie != cookie_str:
        bak_path = CONFIG_FILE.with_suffix(".json.bak")
        try:
            with open(bak_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"   已备份旧配置到: {bak_path}")
        except Exception as e:
            print(f"   备份旧配置失败: {e}")

    config["weibo_cookie"] = cookie_str

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {CONFIG_FILE}")
    print(f"   旧 Cookie 长度: {old_length}")
    print(f"   新 Cookie 长度: {len(cookie_str)}")


def main():
    print("=" * 50)
    print("微博 Cookie 提取工具 (CDP 版)")
    print("=" * 50)

    log_path = Path(__file__).resolve().parent / "chrome_weibo_cdp_debug.log"
    proc = launch_chrome(log_path=log_path)
    if not proc:
        sys.exit(1)

    try:
        print("\n等待 Chrome DevTools Protocol 就绪...")
        if not wait_for_cdp():
            print("\n无法连接到 Chrome 调试端口。")
            if proc.poll() is not None:
                print(f"Chrome 进程已退出，退出码: {proc.returncode}")
            else:
                print("Chrome 进程仍在运行，但调试端口未响应。")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            if hasattr(proc, "_log_fp"):
                proc._log_fp.close()
            if log_path.exists():
                log_text = log_path.read_text(encoding="utf-8", errors="ignore")
                if log_text:
                    print("\nChrome 启动日志（最近 2000 字符）：")
                    print(log_text[-2000:])
            sys.exit(1)

        ws_url = get_page_ws_url()
        if not ws_url:
            print("未能获取到 Chrome 页面调试地址。")
            sys.exit(1)

        weibo_cookies = wait_for_login(ws_url, timeout=300)
        if not weibo_cookies:
            print("\n未获取到可用于爬取的微博登录 Cookie，config.json 未被修改。")
            sys.exit(1)

        # 登录完成，隐藏窗口减少干扰
        hide_chrome_window(proc.pid)

        cookie_str = build_cookie_string(weibo_cookies)
        print(f"\n获取到 {len(weibo_cookies)} 个微博相关 Cookie: {', '.join(c['name'] for c in weibo_cookies)}")
        write_config(cookie_str)

    except KeyboardInterrupt:
        print("\n\n用户取消，正在关闭 Chrome...")
        sys.exit(1)
    finally:
        print("\n正在关闭由脚本启动的 Chrome...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        if hasattr(proc, "_log_fp"):
            proc._log_fp.close()


if __name__ == "__main__":
    main()
