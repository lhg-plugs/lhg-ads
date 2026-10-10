#!/usr/bin/env python3
"""lhg-ads 硬门②（警告级，不拦截）：写投放文档时做轻量提醒。

触发：PostToolUse / Write|Edit。只检查 .md/.txt 投放文档：
  - 文档含投放链接却无 utm_ 参数 → 提醒补 UTM
  - 文档提到预算却没有预算分配表 → 提醒补表

只做提醒，永远 exit 0、不拦截写入；内部出错 fail-open。
逃生方式：LHG_ADS_HOOKS_OFF=1（环境变量）可关闭本提醒；
或 /plugin disable lhg-ads 停用整个插件。
零第三方依赖。
"""

import json
import os
import re
import sys

DOC_EXTS = {".md", ".txt", ".markdown"}
URL_RE = re.compile(r"https?://[^\s\)>\]\"']+")


def main() -> int:
    if os.environ.get("LHG_ADS_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""
    if not file_path:
        return 0

    _, ext = os.path.splitext(file_path)
    if ext.lower() not in DOC_EXTS:
        return 0  # 非投放文档：快速放行

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return 0

    warns = []
    urls = URL_RE.findall(text)
    if urls and not any("utm_" in u for u in urls):
        warns.append("文档含 %d 条投放链接但无一带 utm_ 参数，数据将无法归因到渠道/广告组。" % len(urls))
    if re.search(r"预算", text) and not re.search(r"\|.*渠道.*\|", text):
        warns.append("文档提到预算但没有渠道分配表，建议补一张 渠道|预算金额|占比 的表格。")

    if not warns:
        return 0

    msg = (
        "投放文档提醒（lhg-ads）：%s\n%s\n"
        "完整检查请跑 /lhg-ads:audit；关闭本提醒：export LHG_ADS_HOOKS_OFF=1。"
    ) % (file_path, "\n".join("  - " + w for w in warns))
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
