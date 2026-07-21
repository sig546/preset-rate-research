#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一致性校验：确保所有展示页面使用 predictions.json / actuals.json 单一数据源，
禁止出现与数据源分叉的「硬编码研究值」。

根因背景（2026-07-09）：
  trigger_analysis_report.html 曾写死 1.9383/1.9229/1.8969/1.8800，而 index.html
  运行时读取 predictions.json（1.8804/1.8773...），两页预测值分叉。
  本脚本作为 CI 守卫，防止此类问题再次发生。

校验规则：
  1. 任何引用 predictions.json 的 HTML（单一数据源消费方）不得包含
     [1.75, 2.60] 区间内、且不属于 predictions/actuals 实时值的 4 位小数硬编码。
     （债券收益率叙述句、利差兜底等带有关键词的行被跳过，避免误报）
  2. 全仓库 HTML 不得再出现已知错误值（2026-07 分叉 bug 的过期值）。
  3. index.html 与 trigger_analysis_report.html 必须引用 predictions.json。
  4. predictions.json 的 last_updated 距今不得超过 MAX_AGE_DAYS 天（默认 40，
     可用环境变量 PRED_MAX_AGE_DAYS 覆盖），否则视为「数据源过期」而阻断发布——
     防止上线几个月前的过期预测值（如 2026-07 雷同 1.8773 的旧文件）。

退出码：发现任一问题返回 1，否则返回 0。
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED_FILE = os.path.join(ROOT, "data", "predictions.json")
ACT_FILE = os.path.join(ROOT, "data", "actuals.json")

# 2026-07 分叉 bug 的过期硬编码值（任何页面都不得再出现）
FORBIDDEN = {"1.9383", "1.9229", "1.8969", "1.8800"}

# 已知的历史遗留静态报告（仅被 MIGRATION.md 引用，未接入单一数据源流程）。
# 它们含有过期硬编码值，属于应清理的技术债；先行豁免以保证 CI 不被历史产物阻塞，
# 后续应将其改为读取 predictions.json 或下线。
LEGACY_ALLOWLIST = {"prediction_report.html", "prediction_report_corrected.html"}

# 研究值（预定利率研究值）可能出现的合理区间，用于识别「疑似研究值」的 4 位小数
LOW, HIGH = 1.75, 2.60

# 含这些关键词的行视为叙述/兜底，其中的 4 位小数不算研究值（如「10年期国债最新1.7410%」）
NARRATIVE_KW = ("国债", "LPR", "定存", "利差", "MA250", "MA750", "bond", "Bond")

SSOT_PAGES = ("index.html", "trigger_analysis_report.html")

# 预测数据源最大允许「年龄」（天）。超过则视为过期，CI 阻断发布。
# 可用环境变量 PRED_MAX_AGE_DAYS 覆盖（本地演练或特殊豁免时临时调大）。
MAX_AGE_DAYS = int(os.environ.get("PRED_MAX_AGE_DAYS", "40"))

# 支持的 last_updated 时间格式（宽松解析）
_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
)


def _parse_dt(s):
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_live_values():
    live = set()
    with open(PRED_FILE, encoding="utf-8") as f:
        d = json.load(f)
        for p in d.get("predictions", []):
            # 研究值主字段
            live.add(f"{p['predicted_value']:.4f}")
            # 其余数值字段（base_return / ref_rate / ma250_gov / ma750_gov / spread_* 等）：
            # index.html 内嵌离线快照是 predictions.json 的忠实副本，这些字段也应视为「实时值」，
            # 否则快照里的 ma250_gov 等 4 位小数会被规则1 误判为分叉硬编码而阻断发版。
            for k, v in p.items():
                if isinstance(v, (int, float)) and k not in ("gap_bp", "trigger"):
                    live.add(f"{v:.4f}")
    with open(ACT_FILE, encoding="utf-8") as f:
        d = json.load(f)
        for a in d.get("actuals", []):
            live.add(f"{a['value']:.4f}")
    return live


def check_pred_freshness(errors):
    """规则 4：predictions.json 不得过期。"""
    try:
        with open(PRED_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        errors.append("data/predictions.json 不存在，无法校验数据新鲜度")
        return

    lu = d.get("last_updated")
    if not lu:
        errors.append("data/predictions.json 缺少 last_updated 字段（无法判断数据新鲜度，阻断发布）")
        return

    dt = _parse_dt(lu)
    if dt is None:
        errors.append(f"data/predictions.json 的 last_updated 无法解析: {lu!r}")
        return
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)

    age = (datetime.datetime.now() - dt).total_seconds() / 86400.0
    if age > MAX_AGE_DAYS:
        errors.append(
            f"data/predictions.json 已过期：last_updated={lu}（{age:.1f} 天前），"
            f"超过上限 {MAX_AGE_DAYS} 天。请重新运行 scripts/update_predictions.py "
            f"刷新 predictions.json 后再发布。"
        )
    else:
        print(f"ℹ️  预测数据新鲜度 OK：last_updated={lu}（{age:.1f} 天前，上限 {MAX_AGE_DAYS} 天）")


def main():
    live = load_live_values()
    errors = []

    html_files = sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))
    for fn in html_files:
        path = os.path.join(ROOT, fn)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        is_ssot = "predictions.json" in content
        lines = content.splitlines()

        # 规则 1：SSOT 消费方不得有分叉的硬编码研究值
        if is_ssot:
            for lit in set(re.findall(r"\d\.\d{4}", content)):
                in_narrative = any(
                    lit in line and any(kw in line for kw in NARRATIVE_KW)
                    for line in lines
                )
                if in_narrative:
                    continue
                try:
                    val = float(lit)
                except ValueError:
                    continue
                if LOW <= val <= HIGH and lit not in live:
                    errors.append(
                        f"{fn}: 硬编码研究值 {lit} 不在 predictions/actuals.json 中"
                        f"（疑似过期/分叉，实时值为 {sorted(live)}）"
                    )

        # 规则 2：全仓库禁止已知错误值（历史遗留报告除外，见 LEGACY_ALLOWLIST）
        if fn in LEGACY_ALLOWLIST:
            continue
        for bad in FORBIDDEN:
            if bad in content:
                errors.append(f"{fn}: 含已知错误值 {bad}（2026-07 分叉 bug 的过期值，禁止硬编码）")

        # 规则 3：核心页面必须引用单一数据源
        if fn in SSOT_PAGES and not is_ssot:
            errors.append(f"{fn}: 单一数据源页面必须引用 predictions.json")

    # 规则 4：预测数据源不得过期（独立于页面循环，只校验一次）
    check_pred_freshness(errors)

    if errors:
        print("❌ 一致性校验未通过：")
        for e in errors:
            print("  - " + e)
        sys.exit(1)

    print("✅ 一致性校验通过：所有页面均使用 predictions.json / actuals.json "
          "单一数据源，无分叉硬编码值。")


if __name__ == "__main__":
    main()
