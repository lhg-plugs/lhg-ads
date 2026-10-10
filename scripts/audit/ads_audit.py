#!/usr/bin/env python3
"""lhg-ads 确定性投放审计：13 条规则，零第三方依赖。

扫描目标目录下的投放计划/复盘文档（.md / .txt），检查：
  - 红线：效果承诺语、极限/禁用词、密钥泄露（blocker）
  - 完整性：预算分配表、UTM 参数、落地页一致性、复盘指标口径、
    人群定义、优化目标、复盘时间范围（warning）
  - 规范：标题长度、文档日期/版本（nit）

输出 JSON 与人类可读报告；有 blocker 时 exit 2，纯 warning 时 exit 1
（--fail-on blocker 可把 warning 降为通过），干净时 exit 0。

用法：
    python3 ads_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning]

规则文案与检测逻辑均为本项目原创（高层思路受 claude-ads 等开源项目启发，
未复制任何第三方原文与代码；详见 ATTRIBUTION.md）。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-ads/ads-audit"

SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", ".git", "coverage",
    "__pycache__", "vendor", "out",
}
SCAN_EXTS = {".md", ".txt", ".markdown"}

RULES = []


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        RULES.append({
            "id": rule_id, "severity": severity, "category": category,
            "title": title, "detail": detail, "check": fn,
        })
        return fn
    return deco


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file",
                 "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line,
                 snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


def collect_files(target):
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            _, ext = os.path.splitext(f)
            if ext.lower() in SCAN_EXTS:
                out.append(os.path.join(root, f))
    return sorted(out)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def parse_sections(lines):
    """按 markdown 二级/三级标题切分：[(heading, start_line, body_lines)]。"""
    sections = []
    cur_head, cur_start, cur_body = "(全文)", 0, []
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^#{1,3}\s+(.*\S)\s*$", ln)
        if m:
            sections.append((cur_head, cur_start, cur_body))
            cur_head, cur_start, cur_body = m.group(1).strip(), i, []
        else:
            cur_body.append((i, ln))
    sections.append((cur_head, cur_start, cur_body))
    return sections


def sections_matching(sections, *keywords):
    return [(h, s, b) for h, s, b in sections
            if any(k in h for k in keywords)]


def md_tables(body_lines):
    """提取正文中的 markdown 表格：返回 [(header_cells, data_rows)]。"""
    tables = []
    cur = []
    for _, ln in body_lines:
        if re.match(r"^\s*\|.*\|\s*$", ln):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            cur.append(cells)
        else:
            if len(cur) >= 2:
                tables.append((cur[0], cur[2:]))  # 跳过分隔行
            cur = []
    if len(cur) >= 2:
        tables.append((cur[0], cur[2:]))
    return tables


def numbers_in(cell):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", cell)]


# ---------------------------------------------------------------- 红线规则


EFF_PROMISE_RES = [
    re.compile(p) for p in (
        r"稳赚不赔", r"包赚", r"必赚", r"躺赚", r"保证.{0,6}盈利",
        r"承诺.{0,6}ROI", r"保本.{0,4}(收益|盈利|赚钱)",
        r"零风险.{0,4}(投资|理财|赚钱)", r"百分百.{0,4}(赚钱|盈利|成交)",
        r"100%.{0,4}(赚钱|成交|盈利|转化)",
        r"日入.{0,2}\d", r"月入.{0,2}十万",
    )
]


@rule("ADS-EFF-001", "blocker", "效果承诺",
      "投放文案出现效果承诺语",
      "插件只提供方法论与复盘框架，不承诺任何 ROI/转化效果。"
      "出现'稳赚不赔/保证盈利/承诺ROI'等表述即为红线，必须删除或改写为中性描述。")
def check_eff(doc):
    out = []
    for ln_no, ln in doc["lines"]:
        for rx in EFF_PROMISE_RES:
            m = rx.search(ln)
            if m:
                out.append(Finding(
                    "ADS-EFF-001", "blocker", "效果承诺",
                    "投放文案出现效果承诺语", doc["rel"], ln_no,
                    ln.strip()[:80], "命中：%s" % m.group(0)))
                break
    return out


LAW_BANNED_RES = [
    re.compile(p) for p in (
        r"最佳", r"第一(?!手货源)", r"顶级", r"极致", r"首选", r"国家级",
        r"世界级", r"史无前例", r"空前绝后", r"万能", r"包治百病",
        r"祖传秘方", r"神效", r"根治", r"彻底治愈",
    )
]


@rule("ADS-LAW-001", "blocker", "极限词",
      "素材/落地页文案出现极限或禁用词",
      "《广告法》第九条禁用'国家级/最高级/最佳'等绝对化用语。"
      "只在素材清单/标题/创意/文案/落地页章节内检查，策略正文中的中性叙述不计。")
def check_law(doc):
    copy_secs = sections_matching(doc["sections"], "素材", "标题", "创意",
                                  "文案", "脚本", "落地页")
    target = copy_secs if copy_secs else doc["sections"]
    out = []
    for h, _, body in target:
        for ln_no, ln in body:
            for rx in LAW_BANNED_RES:
                m = rx.search(ln)
                if m:
                    out.append(Finding(
                        "ADS-LAW-001", "blocker", "极限词",
                        "素材/落地页文案出现极限或禁用词", doc["rel"],
                        ln_no, ln.strip()[:80],
                        "章节《%s》命中：%s" % (h, m.group(0))))
                    break
    return out


SECRET_RES = [
    re.compile(r"sk_live_[A-Za-z0-9]{8,}"),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"access[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"secret\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
]


@rule("ADS-SEC-001", "blocker", "密钥泄露",
      "文档中出现疑似广告账户密钥",
      "广告账户 API Key / Token 绝不许写进投放文档。"
      "命中即 blocker，删掉并轮换密钥。")
def check_secret(doc):
    out = []
    for ln_no, ln in doc["lines"]:
        for rx in SECRET_RES:
            if rx.search(ln):
                out.append(Finding(
                    "ADS-SEC-001", "blocker", "密钥泄露",
                    "文档中出现疑似广告账户密钥", doc["rel"], ln_no,
                    ln.strip()[:60] + "...", "请删除并轮换该密钥"))
                break
    return out


# ---------------------------------------------------------------- 完整性规则


@rule("ADS-BUD-001", "warning", "预算",
      "提到预算但缺少预算分配表",
      "预算分配表是投放计划的核心交付物：按渠道列出金额与占比。"
      "文档提到'预算'却没有渠道×金额/占比的 markdown 表格时告警。")
def check_budget_table(doc):
    if not re.search(r"预算", doc["text"]):
        return []
    for _, _, body in doc["sections"]:
        for header, _ in md_tables(body):
            if any("渠道" in c for c in header) and \
                    any(("金额" in c or "预算" in c or "占比" in c) for c in header):
                return []
    return [Finding("ADS-BUD-001", "warning", "预算",
                    "提到预算但缺少预算分配表", doc["rel"], 1, "",
                    "补一张 渠道 | 预算金额 | 占比 的 markdown 表格")]


@rule("ADS-BUD-002", "warning", "预算",
      "预算分配表合计口径异常",
      "占比列合计应在 100% 上下（允许 ±1 误差）；"
      "声明了总预算时，各渠道金额合计应与总预算一致。")
def check_budget_sum(doc):
    out = []
    for _, _, body in doc["sections"]:
        for header, rows in md_tables(body):
            if not (any("渠道" in c for c in header) and
                    any(("金额" in c or "预算" in c or "占比" in c) for c in header)):
                continue
            pct_idx = next((i for i, c in enumerate(header) if "占比" in c), None)
            amt_idx = next((i for i, c in enumerate(header) if "金额" in c or "预算" in c), None)
            if pct_idx is not None:
                total = sum(numbers_in(r[pct_idx])[0] for r in rows
                            if pct_idx < len(r) and numbers_in(r[pct_idx]))
                if rows and not (99 <= total <= 101):
                    out.append(Finding(
                        "ADS-BUD-002", "warning", "预算",
                        "预算分配表占比合计 %.1f%%，不是 100%%" % total,
                        doc["rel"], 1, "",
                        "检查占比列是否漏渠道或算错"))
            if amt_idx is not None:
                m = re.search(r"总预算[：:]\s*(\d+(?:\.\d+)?)", doc["text"])
                if m:
                    declared = float(m.group(1))
                    total = sum(numbers_in(r[amt_idx])[0] for r in rows
                                if amt_idx < len(r) and numbers_in(r[amt_idx]))
                    if rows and declared > 0 and abs(total - declared) / declared > 0.01:
                        out.append(Finding(
                            "ADS-BUD-002", "warning", "预算",
                            "预算金额合计 %.0f 与声明总预算 %.0f 不一致"
                            % (total, declared), doc["rel"], 1, "",
                            "核对各渠道金额或总预算数字"))
    return out


URL_RE = re.compile(r"https?://[^\s\)>\]\"']+")


@rule("ADS-UTM-001", "warning", "追踪",
      "投放链接缺少 UTM 参数",
      "没有 utm_source/medium/campaign 的链接，数据无法归因到渠道与广告组。"
      "每条对外投放链接都应带完整 UTM。")
def check_utm(doc):
    out = []
    seen = set()
    for ln_no, ln in doc["lines"]:
        for m in URL_RE.finditer(ln):
            url = m.group(0).rstrip(".,;")
            if url in seen:
                continue
            seen.add(url)
            if "utm_" not in url:
                out.append(Finding(
                    "ADS-UTM-001", "warning", "追踪",
                    "投放链接缺少 UTM 参数", doc["rel"], ln_no,
                    url[:80], "补上 utm_source/medium/campaign"))
                if len(out) >= 5:
                    return out
    return out


PRICE_CLAIM_RE = re.compile(r"¥\s*\d|价格|折|免费|赠送|领取|立减|优惠")


@rule("ADS-LPG-001", "warning", "落地页",
      "素材有价格/权益承诺但缺落地页一致性说明",
      "广告承诺（价格、赠品、优惠）必须在落地页首屏兑现，"
      "否则跳出率与投诉率飙升。素材章节出现价格/权益承诺时，"
      "文档应有专门的落地页一致性核对章节。")
def check_landing(doc):
    if not sections_matching(doc["sections"], "落地页"):
        copy_secs = sections_matching(doc["sections"], "素材", "标题", "创意", "文案")
        target = copy_secs if copy_secs else doc["sections"]
        for h, _, body in target:
            for ln_no, ln in body:
                if PRICE_CLAIM_RE.search(ln):
                    return [Finding(
                        "ADS-LPG-001", "warning", "落地页",
                        "素材有价格/权益承诺但缺落地页一致性说明",
                        doc["rel"], ln_no, ln.strip()[:80],
                        "增加'落地页一致性'章节，逐条核对广告承诺在落地页首屏可兑现")]
    return []


METRIC_RES = [
    re.compile(r"\bCTR\b"), re.compile(r"\bCVR\b"), re.compile(r"\bROAS\b"),
    re.compile(r"\bCPC\b"), re.compile(r"\bCPA\b"), re.compile(r"\bCPM\b"),
    re.compile(r"点击率"), re.compile(r"转化率"), re.compile(r"投产比"),
]


@rule("ADS-REV-001", "warning", "复盘",
      "复盘提到指标但缺少口径定义",
      "CTR/CVR/ROAS 等指标在不同平台口径不同（点击归因窗口、转化定义）。"
      "复盘文档应有'指标口径'章节写清每个指标的定义与统计窗口，否则结论不可比。")
def check_metric_def(doc):
    if any(rx.search(doc["text"]) for rx in METRIC_RES):
        if not re.search(r"口径|定义", doc["text"]):
            return [Finding("ADS-REV-001", "warning", "复盘",
                            "复盘提到指标但缺少口径定义", doc["rel"], 1, "",
                            "增加'指标口径'章节：每个指标的定义、归因窗口、数据来源")]
    return []


@rule("ADS-AUD-001", "warning", "策略",
      "投放策略缺少人群/定向定义",
      "没有人群定义就没有出价依据。投放策略章节应写清："
      "人群画像、定向方式（兴趣/关键词/再营销）、排除人群。")
def check_audience(doc):
    if sections_matching(doc["sections"], "投放策略", "策略") or \
            re.search(r"预算", doc["text"]):
        if not re.search(r"人群|受众|定向", doc["text"]):
            return [Finding("ADS-AUD-001", "warning", "策略",
                            "投放策略缺少人群/定向定义", doc["rel"], 1, "",
                            "补充人群画像与定向方式")]
    return []


@rule("ADS-KPI-001", "warning", "策略",
      "投放计划未声明优化目标",
      "没有优化目标就无法判断投放成败。应声明："
      "优化目标（转化/加购/留资）、目标 CPA 或目标 ROAS、考核周期。")
def check_kpi(doc):
    if re.search(r"预算|投放计划", doc["text"]):
        if not re.search(r"优化目标|考核指标|KPI|目标CPA|目标ROAS|目标 CPA|目标 ROAS", doc["text"]):
            return [Finding("ADS-KPI-001", "warning", "策略",
                            "投放计划未声明优化目标", doc["rel"], 1, "",
                            "补充优化目标与目标 CPA/ROAS")]
    return []


DATE_RE = re.compile(r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}|20\d{2}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日")


@rule("ADS-DAT-001", "warning", "复盘",
      "复盘文档缺少时间范围",
      "没有时间范围的复盘无法复现、无法对比。复盘章节应写清数据起止日期。")
def check_review_dates(doc):
    if sections_matching(doc["sections"], "复盘"):
        if not DATE_RE.search(doc["text"]):
            return [Finding("ADS-DAT-001", "warning", "复盘",
                            "复盘文档缺少时间范围", doc["rel"], 1, "",
                            "在复盘章节注明数据起止日期，如 2026-10-01 至 2026-10-07")]
    return []


# ---------------------------------------------------------------- 规范规则


@rule("ADS-FMT-001", "nit", "规范",
      "广告标题疑似超长",
      "信息流/搜索广告标题建议 ≤30 字（中文），超长会被截断。"
      "标题章节中超过 30 字的行会被标记。")
def check_title_len(doc):
    out = []
    title_secs = sections_matching(doc["sections"], "标题", "素材")
    target = title_secs if title_secs else []
    for h, _, body in target:
        for ln_no, ln in body:
            s = ln.strip().lstrip("-*0123456789. ").strip()
            if len(s) > 30 and not s.startswith("|") and not s.startswith("#"):
                out.append(Finding(
                    "ADS-FMT-001", "nit", "规范",
                    "广告标题疑似超长（%d 字）" % len(s), doc["rel"],
                    ln_no, s[:60], "精简到 30 字以内，核心卖点前置"))
                if len(out) >= 5:
                    return out
    return out


@rule("ADS-DOC-001", "nit", "规范",
      "文档缺少日期或版本",
      "投放文档应带日期/版本号，方便回溯哪一版策略对应哪一段数据。")
def check_doc_meta(doc):
    if not re.search(r"日期|版本|20\d{2}[-/年]", doc["text"]):
        return [Finding("ADS-DOC-001", "nit", "规范",
                        "文档缺少日期或版本", doc["rel"], 1, "",
                        "在文档顶部加 日期 / 版本")]
    return []


# ---------------------------------------------------------------- 主流程


def audit_doc(path, root):
    text = read_text(path)
    lines = list(enumerate(text.split("\n"), 1))
    doc = {
        "path": path,
        "rel": os.path.relpath(path, root),
        "text": text,
        "lines": lines,
        "sections": parse_sections([ln for _, ln in lines]),
    }
    findings = []
    for r in RULES:
        try:
            findings.extend(r["check"](doc))
        except Exception as e:  # 单条规则出错不影响整体
            findings.append(Finding(
                r["id"], "nit", "引擎", "规则执行异常：%s" % e,
                doc["rel"], 0, "", ""))
    return findings


def main():
    ap = argparse.ArgumentParser(description="lhg-ads 确定性投放审计")
    ap.add_argument("--target", required=True, help="待扫描目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning"],
                    default="blocker", help="达到该级别即非零退出")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    files = collect_files(target)
    findings = []
    for f in files:
        findings.extend(audit_doc(f, target))

    sev_rank = {"blocker": 0, "warning": 1, "nit": 2}
    findings.sort(key=lambda x: (sev_rank.get(x.severity, 3), x.file, x.line))
    counts = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    summary = {
        "tool": TOOL, "version": VERSION, "target": target,
        "files_scanned": len(files), "rules_run": len(RULES),
        "blocker": counts["blocker"], "warning": counts["warning"],
        "nit": counts["nit"],
    }

    if args.format == "json":
        print(json.dumps({"summary": summary,
                          "findings": [f.to_dict() for f in findings]},
                         ensure_ascii=False, indent=2))
    else:
        print("lhg-ads 投放审计：%s" % target)
        print("扫描 %d 个文件，运行 %d 条规则" % (len(files), len(RULES)))
        print("blocker=%d warning=%d nit=%d"
              % (counts["blocker"], counts["warning"], counts["nit"]))
        for f in findings:
            print("[%s][%s] %s:%s %s"
                  % (f.severity, f.rule_id, f.file, f.line, f.title))
            if f.snippet:
                print("    %s" % f.snippet)
            if f.detail:
                print("    → %s" % f.detail)

    if counts["blocker"] > 0:
        return 2
    if args.fail_on == "warning" and counts["warning"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
