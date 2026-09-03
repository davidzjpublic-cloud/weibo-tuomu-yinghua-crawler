# -*- coding: utf-8 -*-
"""
Chrome DevTools Protocol (CDP) 共享基础设施。

供 extract_quark_cookie_cdp.py 和 extract_weibo_cookie_cdp.py 复用。
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

# Windows 下 stdout/stderr 常为 GBK 编码，输出 emoji（如 ✅）会抛 UnicodeEncodeError，
# 降级为替换字符避免写配置成功后脚本仍以异常退出。
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass

_requests_session = None


def get_requests_session() -> requests.Session:
    """获取一个不走系统代理的 requests Session（单例）。"""
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


def launch_chrome(
    profile_dir: Path,
    port: int,
    target_url: str,
    log_path: Path = None,
) -> subprocess.Popen:
    """启动带远程调试端口的 Chrome，使用独立的配置目录。"""
    chrome = find_chrome_exe()
    if not chrome:
        print("未找到 chrome.exe，请确认 Google Chrome 已安装。")
        return None

    profile_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile_dir}",
        "--profile-directory=Default",
        "--no-first-run",
        "--no-default-browser-check",
        target_url,
    ]
    print(f"正在启动 Chrome: {chrome}")
    print(f"独立配置目录: {profile_dir}")
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


def wait_for_cdp(port: int, timeout: int = 30) -> bool:
    """等待 Chrome DevTools Protocol 可用。"""
    url = f"http://127.0.0.1:{port}/json/version"
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


def get_page_ws_url(port: int, domain_hint: str, fallback_url: str) -> str:
    """获取一个可用页面的 WebSocket 调试地址。

    Args:
        port: Chrome 远程调试端口。
        domain_hint: 优先匹配的 URL 关键词（如 "quark" 或 "weibo"）。
        fallback_url: 无匹配页面时打开的新页面 URL。
    """
    list_url = f"http://127.0.0.1:{port}/json/list"
    session = get_requests_session()
    r = session.get(list_url, timeout=10)
    r.raise_for_status()
    pages = r.json()

    for page in pages:
        if page.get("type") == "page" and domain_hint in (page.get("url") or ""):
            return page.get("webSocketDebuggerUrl")
    for page in pages:
        if page.get("type") == "page":
            return page.get("webSocketDebuggerUrl")

    new_url = f"http://127.0.0.1:{port}/json/new?{fallback_url}"
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


def build_cookie_string(cookies: list) -> str:
    """将 CDP 返回的 Cookie 列表拼接为 HTTP Cookie 字符串。"""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def write_config(cookie_str: str, config_key: str, config_file: Path) -> None:
    """将 Cookie 字符串写入 config.json 的指定字段，并保留一份备份。"""
    config = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"警告：{config_file} 解析失败，将重新创建: {e}")
            config = {}
        except Exception as e:
            print(f"读取 {config_file} 失败: {e}")
            raise

    old_cookie = config.get(config_key, "")
    old_length = len(old_cookie)

    if old_cookie and old_cookie != cookie_str:
        bak_path = config_file.with_suffix(".json.bak")
        try:
            with open(bak_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"   已备份旧配置到: {bak_path}")
        except Exception as e:
            print(f"   备份旧配置失败: {e}")

    config[config_key] = cookie_str

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {config_file}")
    print(f"   旧 Cookie 长度: {old_length}")
    print(f"   新 Cookie 长度: {len(cookie_str)}")


def run_cdp_flow(
    tool_name: str,
    profile_dir: Path,
    port: int,
    target_url: str,
    domain_hint: str,
    log_filename: str,
    config_key: str,
    config_file: Path,
    wait_for_login_fn,
) -> None:
    """CDP Cookie 提取的通用主流程。

    Args:
        tool_name: 工具名（用于标题显示）。
        profile_dir: Chrome 独立配置目录。
        port: 远程调试端口。
        target_url: Chrome 启动后打开的 URL。
        domain_hint: 优先匹配的页面 URL 关键词。
        log_filename: Chrome 启动日志文件名。
        config_key: config.json 中的 Cookie 字段名。
        config_file: config.json 路径。
        wait_for_login_fn: 等待登录的回调，签名为 (ws_url: str, timeout: int) -> list。
    """
    print("=" * 50)
    print(tool_name)
    print("=" * 50)

    log_path = Path(__file__).resolve().parent / log_filename
    proc = launch_chrome(profile_dir, port, target_url, log_path=log_path)
    if not proc:
        import sys
        sys.exit(1)

    try:
        print("\n等待 Chrome DevTools Protocol 就绪...")
        if not wait_for_cdp(port):
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
            import sys
            sys.exit(1)

        ws_url = get_page_ws_url(port, domain_hint, target_url)
        if not ws_url:
            print("未能获取到 Chrome 页面调试地址。")
            import sys
            sys.exit(1)

        site_cookies = wait_for_login_fn(ws_url, timeout=300)
        if not site_cookies:
            print(f"\n未获取到可用的登录 Cookie，{config_file} 未被修改。")
            import sys
            sys.exit(1)

        hide_chrome_window(proc.pid)
        cookie_str = build_cookie_string(site_cookies)
        print(f"\n获取到 {len(site_cookies)} 个 Cookie: {', '.join(c['name'] for c in site_cookies)}")
        write_config(cookie_str, config_key, config_file)

    except KeyboardInterrupt:
        print("\n\n用户取消，正在关闭 Chrome...")
        import sys
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
