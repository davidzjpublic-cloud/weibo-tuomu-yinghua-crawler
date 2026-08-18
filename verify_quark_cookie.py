#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证当前 config.json 中的 quark_cookie 是否能调用夸克 API。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quark import QuarkClient

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"
TEST_URL = "https://pan.quark.cn/s/5447f0c8ec94"

def main():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    cookie = config.get("quark_cookie", "")
    print(f"quark_cookie 长度: {len(cookie)}")
    print(f"包含 __pus: {'__pus' in cookie}")
    print(f"包含 __puus: {'__puus' in cookie}")
    print(f"包含 __kp: {'__kp' in cookie}")

    client = QuarkClient(cookie)
    files = client.list_share_files(TEST_URL)
    print(f"\nlist_share_files 返回 {len(files)} 个文件")
    if files:
        for f in files[:3]:
            print(" ", f.get("file_name"), f.get("fid"))
    else:
        print("未能获取文件列表，Cookie 可能仍无效。")

    print("\n测试个人网盘目录查找/创建...")
    dir_fid = client.find_or_create_dir("来自：分享/【拓临】")
    if dir_fid:
        print(f"目录 fid: {dir_fid}")
    else:
        print("目录查找/创建失败")

if __name__ == "__main__":
    main()
