# -*- coding: utf-8 -*-
"""
比较两个文件名列表文件，输出差异报告。
"""

import sys
from pathlib import Path


def parse_filename_line(line: str):
    """解析形如 '1. 爱与输 Aimer perdre 2024 （...）' 的行。"""
    line = line.strip()
    if not line:
        return None, None
    # 去掉序号前缀
    if '. ' in line:
        idx, content = line.split('. ', 1)
    else:
        content = line
    return content


def compare_files(baseline_path: str, actual_path: str):
    with open(baseline_path, 'r', encoding='utf-8') as f:
        baseline_lines = [parse_filename_line(l) for l in f if l.strip()]
    with open(actual_path, 'r', encoding='utf-8') as f:
        actual_lines = [parse_filename_line(l) for l in f if l.strip()]

    max_len = max(len(baseline_lines), len(actual_lines))
    diffs = []
    for i in range(max_len):
        b = baseline_lines[i] if i < len(baseline_lines) else None
        a = actual_lines[i] if i < len(actual_lines) else None
        if b != a:
            diffs.append((i + 1, b, a))

    print(f"基准行数: {len(baseline_lines)}, 实际行数: {len(actual_lines)}, 差异行数: {len(diffs)}")
    print()
    for idx, b, a in diffs:
        print(f"第 {idx} 行:")
        print(f"  基准: {b}")
        print(f"  实际: {a}")
        print()

    return diffs


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        baseline = sys.argv[1]
        actual = sys.argv[2]
    else:
        baseline = "filenames_2026-08-16_0.txt"
        actual = "filenames_2026-08-16.txt"
    compare_files(baseline, actual)
