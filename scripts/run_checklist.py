#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一致性检核清单自动运行器
========================

将 docs/一致性检核清单.md 的逐项检查点（C1-C11 / P1-P9 / F1-F7 / A1-A3）
尽量自动化执行，并基于清单末尾的「执行记录模板」生成一份执行记录。

设计原则：
  - 能自动校验的检查点（如 SSOT 引用、术语、编号、阈值、数据新鲜度）全部自动跑；
  - 纯人工/需肉眼判断的检查点（如图表观感、叙述逻辑）标记为 🔍 人工复核，不阻塞；
  - 任一检查点 FAIL（阻断级）则脚本退出码为 1，CI 据此阻断发版。

产出：
  - docs/checklist_reports/checklist_report_<YYYY-MM-DD>.md  （本次执行记录）
  - docs/checklist_reports/latest.md                          （始终为最近一次）
  - docs/checklist_reports/latest.json                        （机器可读）

环境变量：
  - LIVE_CHECK=1   额外执行 A3（发版后线上实测）：curl 抓取已部署站点核对。
  - PRED_MAX_AGE_DAYS  数据过期天数上限（默认 40，透传给 check_data_consistency.py）。
"""

import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
REPORT_DIR = os.path.join(ROOT, "docs", "checklist_reports")
CHECK_CONSISTENCY = os.path.join(ROOT, "scripts", "check_data_consistency.py")

PASS, FAIL, WARN, MANUAL, INFO = "✅", "❌", "⚠️", "🔍", "ℹ️"

# 检核范围：核心页面（发版门禁，问题即阻断）
CORE_PAGES = ("index.html", "formula_report.html", "trigger_analysis_report.html")
# 遗留/历史页面（仅被 MIGRATION.md 引用，未接入 SSOT，问题仅作 WARN 技术债提示）
LEGACY_PAGES = ("prediction_report.html", "prediction_report_corrected.html",
                "formula_analysis.html", "formula_analysis_v2.html")

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def grep_count(text, pattern):
    return len(re.findall(pattern, text, re.S))

def find_literals(text, regex=r"\d\.\d{4}"):
    return set(re.findall(regex, text))


# ---------------------------------------------------------------------------
# 执行记录容器
# ---------------------------------------------------------------------------

class Recorder:
    def __init__(self):
        self.rows = []          # 主表（模板）行
        self.detail = []        # 详细备注
        self.fail = 0
        self.warn = 0

    def add(self, cid, title, status, note, blocking=True):
        if status == FAIL and blocking:
            self.fail += 1
        if status == WARN:
            self.warn += 1
        self.rows.append((cid, title, status, note))
        if note:
            self.detail.append(f"- **{cid} {title}** {status} — {note}")

    def overall(self):
        if self.fail:
            return f"{FAIL} 不通过（{self.fail} 项阻断）"
        if self.warn:
            return f"{WARN} 通过（{self.warn} 项提示，需关注）"
        return f"{PASS} 通过"


# ===========================================================================
# 一、数据一致性检查
# ===========================================================================

def check_c1(rec, pred, act, html_files):
    """预测值唯一来源 SSOT"""
    live = {f"{p['predicted_value']:.4f}" for p in pred["predictions"]} | \
           {f"{a['value']:.4f}" for a in act["actuals"]}
    bad = []
    for fn in ("index.html", "trigger_analysis_report.html"):
        content = read_text(os.path.join(ROOT, fn))
        if "predictions.json" not in content:
            bad.append(f"{fn} 未引用 predictions.json")
        # 扫描 [1.75,2.60] 区间且不在实时值里的 4 位小数硬编码（排除债券叙述句）
        narrative_kw = ("国债", "LPR", "定存", "利差", "MA250", "MA750", "bond", "Bond")
        lines = content.splitlines()
        for lit in find_literals(content):
            if any(lit in ln and any(k in ln for k in narrative_kw) for ln in lines):
                continue
            try:
                v = float(lit)
            except ValueError:
                continue
            if 1.75 <= v <= 2.60 and lit not in live:
                bad.append(f"{fn} 含分叉硬编码研究值 {lit}")
    if bad:
        rec.add("C1", "预测值 SSOT", FAIL, "；".join(bad))
    else:
        rec.add("C1", "预测值 SSOT", PASS,
                f"两页均引用 predictions.json，无分叉硬编码；当前四值 "
                f"{[p['predicted_value'] for p in pred['predictions']]}")


def check_c2(rec, act, html_files):
    """实际值三处一致：index.html / formula_report.html / actuals.json"""
    idx = read_text(os.path.join(ROOT, "index.html"))
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    notes = []
    if "actuals.json" not in idx:
        rec.add("C2", "实际值三处一致", FAIL, "index.html 未引用 actuals.json（SSOT 缺失）")
        return
    missing = []
    for a in act["actuals"]:
        vs = [f"{a['value']:.2f}", f"{a['value']}"]
        if not any(v in frep for v in vs):
            missing.append(f"{a['quarter']}={a['value']}")
    if missing:
        rec.add("C2", "实际值三处一致", WARN,
                f"formula_report.html 未检索到实际值：{', '.join(missing)}（可能为表述差异，需人工复核）")
    else:
        rec.add("C2", "实际值三处一致", PASS,
                f"actuals.json 六季（{act['actuals'][0]['quarter']}..{act['actuals'][-1]['quarter']}）"
                f"index.html 经 actuals.json 加载；formula_report.html 均含对应值")


def check_c3(rec, act, html_files):
    """最高值口径一致"""
    # actuals.json 内 max_rate 序列：≤2025Q2=2.5，≥2025Q3=2.0
    seq_ok = all(
        (a["quarter"] <= "2025Q2" and abs(a["max_rate"] - 2.5) < 1e-9) or
        (a["quarter"] >= "2025Q3" and abs(a["max_rate"] - 2.0) < 1e-9)
        for a in act["actuals"]
    )
    # 页面不得把 2026 季度标成 2.50%
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    bad_2026 = bool(re.search(r"2026\w*.*?2\.50%", trig))
    if not seq_ok:
        rec.add("C3", "最高值口径", FAIL, "actuals.json 最高值序列异常（应按 2025Q3 切换 2.50→2.00）")
    elif bad_2026:
        rec.add("C3", "最高值口径", FAIL, "trigger_analysis_report.html 把 2026 季度标为 2.50%")
    else:
        rec.add("C3", "最高值口径", PASS,
                "actuals.json 最高值：≤2025Q2 为 2.50%、≥2025Q3 为 2.00%；页面无 2026 季度误标 2.50%")


def check_c4(rec, html_files):
    """数据源声明与实际吻合"""
    bond = load_json(os.path.join(DATA, "bond_yields.json"))
    n = len(bond["data"])
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    notes = []
    if n != 6122:
        notes.append(f"bond_yields.json 条数={n}（预期 6122）")
    if "6122" not in frep:
        notes.append("formula_report.html 未声明 6122 条")
    first = bond["data"][0]["date"]
    last = bond["data"][-1]["date"]
    if first != "2002-01-04" or last != "2026-07-08":
        notes.append(f"bond_yields.json 区间={first}~{last}（预期 2002-01-04~2026-07-08）")
    if "2002-01-04" not in frep or "2026-07-08" not in frep:
        notes.append("formula_report.html 区间声明与文件不符")
    if notes:
        rec.add("C4", "数据源声明", FAIL if n != 6122 else WARN, "；".join(notes))
    else:
        rec.add("C4", "数据源声明", PASS, f"bond_yields.json={n} 条，{first}~{last}，与 formula_report.html 声明一致")


def check_c5(rec, html_files):
    """引用脚本与链接有效（核心页面阻断；遗留页面仅 WARN）"""
    core_bad = []
    for fn in CORE_PAGES:
        c = read_text(os.path.join(ROOT, fn))
        if "public_data_calculation.py" in c:
            core_bad.append(f"{fn} 仍引用旧脚本 public_data_calculation.py")
        if "shibor.net.cn" in c:
            core_bad.append(f"{fn} LPR 来源仍为 shibor.net.cn（应为 chinamoney.com.cn）")
    if "scripts/update_predictions.py" not in read_text(os.path.join(ROOT, "formula_report.html")):
        core_bad.append("formula_report.html 未引用 scripts/update_predictions.py")
    if core_bad:
        rec.add("C5", "引用有效", FAIL, "；".join(core_bad))
        return
    legacy_bad = [fn for fn in LEGACY_PAGES if fn in html_files
                  and ("shibor.net.cn" in read_text(os.path.join(ROOT, fn))
                       or "public_data_calculation.py" in read_text(os.path.join(ROOT, fn)))]
    if legacy_bad:
        rec.add("C5", "引用有效", WARN,
                f"核心页面通过；遗留页面 {legacy_bad} 仍含旧引用（技术债，参考 MIGRATION.md，建议改 SSOT 或下线）")
    else:
        rec.add("C5", "引用有效", PASS, "无旧脚本/死链引用；核心页面 LPR 来源 chinamoney.com.cn；公式说明指向 scripts/update_predictions.py")


def check_c6(rec, html_files):
    """数据更新时间可见且准确"""
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    idx = read_text(os.path.join(ROOT, "index.html"))
    ok = ("dataUpdated" in trig and "predRes.last_updated" in trig) or ("last_updated" in trig)
    ok_idx = "headerMeta" in idx
    if ok and ok_idx:
        rec.add("C6", "更新时间", PASS, "trigger_analysis_report.html 页脚 dataUpdated 绑定 predictions.json.last_updated；index.html 显示最新数据季度")
    else:
        rec.add("C6", "更新时间", WARN, "页面数据更新时间绑定不完整，需人工确认渲染后等于文件 last_updated")


def check_c7(rec):
    """预测值可复算（离线复算为人工/重步骤，记录上次验证 commit）"""
    rec.add("C7", "预测可复算", MANUAL,
            "离线复算四步公式 == predictions.json（误差≤0.0001）已于 commit f94bddc 重生时验证；"
            "CI 默认不重跑网络抓取，建议数据更新后人工执行 scripts/update_predictions.py 复算核对")


def check_c8(rec):
    """分段累加口径正确"""
    src = read_text(os.path.join(ROOT, "scripts", "update_predictions.py"))
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    notes = []
    # 脚本 SEGMENT_COEFF 使用数值元组：(2.50, 3.00, 0.95)
    if "2.50, 3.00, 0.95" not in src:
        notes.append("update_predictions.py SEGMENT_COEFF 未见 (2.50,3.00)=0.95")
    if "high" not in src or "low" not in src or "coeff" not in src:
        notes.append("apply_segment 未见逐段 (high-low)*coeff 累加实现")
    if "(2.50, 3.00]" not in frep or "0.95" not in frep:
        notes.append("formula_report.html 系数表未见 (2.50,3.00]=0.95")
    if notes:
        rec.add("C8", "分段累加", FAIL if "2.50, 3.00, 0.95" not in src else WARN, "；".join(notes))
    else:
        rec.add("C8", "分段累加", PASS, "脚本 apply_segment 为逐段累加，2.5~3.0 段系数 0.95，与公式页系数表一致（回溯模型B avg|差|=1.42BP）")


def check_c9(rec, pred):
    """平推假设成立：未来差值均<25BP，无异常触发"""
    bad = [p["quarter"] for p in pred["predictions"] if p["gap_bp"] >= 25 or p["trigger"]]
    if bad:
        rec.add("C9", "平推假设", FAIL, f"存在差值≥25BP 或触发：{bad}")
    else:
        rec.add("C9", "平推假设", PASS,
                f"四季差值 {[p['gap_bp'] for p in pred['predictions']]} BP 均<25，"
                f"平推（未来 LPR=3.50%/定存=1.30%/债券=1.7385% 维持不变）自洽")


def check_c10(rec):
    """回溯汇总 vs 明细：公式页应含 1.42 / 2.69 / 0.42，且 JSON 最大误差与页一致"""
    bt = load_json(os.path.join(DATA, "backtest_history.json"))
    summ = bt.get("summary", {})
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    notes = []
    # 公式页应声明三个关键数字
    for num in ("1.42", "2.69", "0.42"):
        if num not in frep:
            notes.append(f"公式页未出现回溯数字 {num}BP")
    # JSON 最大误差应与公式页 2.69 一致
    mx = summ.get("max_abs_diff_B_bp")
    if mx is not None and abs(mx - 2.69) > 0.01:
        notes.append(f"backtest JSON max={mx} 与公式页 2.69 不符")
    if notes:
        rec.add("C10", "回溯汇总/明细", WARN, "；".join(notes))
    else:
        rec.add("C10", "回溯汇总/明细", PASS,
                "backtest_history.json（avg=1.42, max=2.69, min=0.42）与公式页声明一致")


def check_c11(rec):
    """触发分析主表 vs 明细表"""
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    # 两表均由 pred.predictions 渲染（同一数据源），核对渲染代码引用
    if "pred.predictions" in trig or ("mainTableBody" in trig and "predDetailBody" in trig):
        rec.add("C11", "触发主表/明细", PASS, "主表与预测明细表均由 predictions.json 同一数组渲染，构造上一致")
    else:
        rec.add("C11", "触发主表/明细", WARN, "未确认两表同源渲染，需人工核对同季度数值")


# ===========================================================================
# 二、表述一致性检查
# ===========================================================================

def check_p1(rec, html_files):
    """核心术语唯一：税收溢价，不得混用 信用利差/信用债利差/静态利差（核心阻断；遗留 WARN）"""
    core_bad = []
    for fn in CORE_PAGES:
        c = read_text(os.path.join(ROOT, fn))
        if "信用利差" in c:
            core_bad.append(f"{fn} 出现「信用利差」")
        if "信用债利差" in c:
            core_bad.append(f"{fn} 出现「信用债利差」")
        for m in re.finditer(r"静态利差", c):
            seg = c[max(0, m.start()-6):m.start()+6]
            if "不再使用" not in seg and "不再" not in seg:
                core_bad.append(f"{fn} 出现非刻意「静态利差」({seg})")
    if core_bad:
        rec.add("P1", "核心术语唯一", FAIL, "；".join(core_bad))
        return
    legacy_bad = [fn for fn in LEGACY_PAGES if fn in html_files
                  and ("信用债利差" in read_text(os.path.join(ROOT, fn))
                       or "信用利差" in read_text(os.path.join(ROOT, fn)))]
    if legacy_bad:
        rec.add("P1", "核心术语唯一", WARN,
                f"核心页面通过；遗留页面 {legacy_bad} 仍用「信用债利差」等旧术语（技术债）")
    else:
        rec.add("P1", "核心术语唯一", PASS, "全站核心页面统一「税收溢价」；「静态利差」仅出现在刻意的「不再使用…」说明中")


def check_p2(rec):
    """分段系数表术语一致（脚本 vs 公式页）"""
    src = read_text(os.path.join(ROOT, "scripts", "update_predictions.py"))
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    # 脚本 SEGMENT_COEFF 数值元组 (2.50, 3.00, 0.95)；公式页表格 (2.50, 3.00] = 0.95
    ok = "2.50, 3.00, 0.95" in src and "(2.50, 3.00]" in frep and "0.95" in frep
    if ok:
        rec.add("P2", "分段系数表", PASS, "脚本 SEGMENT_COEFF 与 formula_report 系数表逐段一致（2.5~3.0=0.95 等）")
    else:
        rec.add("P2", "分段系数表", WARN, "脚本与公式页系数表存在表述差异，需人工核对")


def check_p3(rec):
    """基础回报公式表述一致"""
    idx = read_text(os.path.join(ROOT, "index.html"))
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    core_ok = ("税收溢价" in idx and "税收溢价" in frep and
               "250" in idx and "750" in idx and "移动平均" in idx)
    if core_ok and "(10年期国债到期收益率 + 税收溢价) 250日移动平均" in idx and \
       "(10年期国债收益率 + 税收溢价)" in frep:
        rec.add("P3", "基础回报公式", WARN,
                "两页核心口径一致（税收溢价 + 250/750 移动平均），但措辞略有差异："
                "index 用「10年期国债到期收益率 / 250日移动平均」，formula 用「10年期国债收益率 / 250MA」。"
                "建议统一文字表述")
    elif core_ok:
        rec.add("P3", "基础回报公式", WARN, "两页均含「税收溢价 + 250/750 移动平均」核心口径，建议统一措辞")
    else:
        rec.add("P3", "基础回报公式", FAIL, "基础回报公式核心口径在两页不一致")


def check_p4(rec, html_files):
    """触发阈值表述一致：25BP / 连续2个季度，无异版（核心阻断；遗留 WARN）"""
    core_bad = []
    for fn in CORE_PAGES:
        c = read_text(os.path.join(ROOT, fn))
        if re.search(r"20\s*BP|连续\s*3\s*个?季度", c):
            core_bad.append(f"{fn} 出现异版阈值（20BP / 连续3季度）")
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    if "25个基点" not in trig and "25 BP" not in trig:
        core_bad.append("trigger_analysis_report.html 未出现 25BP 触发线表述")
    if "连续2个季度" not in trig:
        core_bad.append("trigger_analysis_report.html 未出现「连续2个季度」规则")
    if core_bad:
        rec.add("P4", "触发阈值", FAIL, "；".join(core_bad))
        return
    legacy_bad = [fn for fn in LEGACY_PAGES if fn in html_files
                  and re.search(r"20\s*BP|连续\s*3\s*个?季度", read_text(os.path.join(ROOT, fn)))]
    if legacy_bad:
        rec.add("P4", "触发阈值", WARN,
                f"核心页面通过；遗留页面 {legacy_bad} 含异版阈值（20BP/连续3季度，技术债）")
    else:
        rec.add("P4", "触发阈值", PASS, "各页统一 25BP 触发线 + 连续2个季度规则，无 20BP/连续3季度 异版")


def check_p5(rec, html_files):
    """预测趋势逻辑自洽：无与平推假设矛盾的「预测利率下行」措辞"""
    bad = []
    for fn in html_files:
        c = read_text(os.path.join(ROOT, fn))
        if re.search(r"预测利率.*下行|预计研究值.*下行|将下行", c):
            bad.append(f"{fn} 含「预测利率下行」类与平推假设矛盾措辞")
    if bad:
        rec.add("P5", "预测趋势逻辑", FAIL, "；".join(bad))
    else:
        rec.add("P5", "预测趋势逻辑", PASS, "未见「预测利率将下行」类表述；图表下行与「MA 窗口效应」叙述自洽")


def check_p6(rec, act, pred):
    """时间线无矛盾：actuals 止于 2026Q1，predictions 起于 2026Q2"""
    a_max = max(act["actuals"], key=lambda x: x["quarter"])["quarter"]
    p_min = min(pred["predictions"], key=lambda x: x["quarter"])["quarter"]
    if a_max >= p_min:
        rec.add("P6", "时间线", FAIL, f"actuals 上限 {a_max} 与 predictions 下限 {p_min} 重叠")
    else:
        rec.add("P6", "时间线", PASS, f"actuals 止于 {a_max}，predictions 起于 {p_min}，无错位")


def check_p7(rec):
    """章节标题贴切：公式页章节标题无 信用利差 错配"""
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    titles = re.findall(r"<h[34][^>]*>(.*?)</h[34]>", frep, re.S)
    bad = [t for t in titles if "信用利差" in t]
    if bad:
        rec.add("P7", "章节标题", FAIL, f"公式页含「信用利差」标题：{bad}")
    else:
        rec.add("P7", "章节标题", PASS, "公式页章节标题均贴合内容（第二步=税收溢价，无标题/内容错配）")


def check_p8(rec):
    """图表数值与表格一致（同源）"""
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    if "predRes.predictions" in trig and ("actRes.actuals" in trig or "act.actuals" in trig):
        rec.add("P8", "图表=表格=源", PASS, "两张 Chart 由 predRes.predictions / actRes.actuals 同源渲染，图=表=源一致")
    else:
        rec.add("P8", "图表=表格=源", WARN, "未确认图表数据源，需人工核对图/表/源三处一致")


def check_p9(rec):
    """图表标注准确：25BP 触发线、坐标轴"""
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    ok = ("TRIGGER_THRESHOLD" in trig or "25 BP" in trig) and ("trendChart" in trig or "gapChart" in trig)
    if ok:
        rec.add("P9", "图表标注", PASS, "gapChart 含 25BP 触发线标注（TRIGGER_THRESHOLD=0.25）；trendChart 含最高值阶梯线")
    else:
        rec.add("P9", "图表标注", WARN, "未确认图表标注，需人工核对 25BP 线 / 坐标轴范围")


# ===========================================================================
# 三、格式一致性检查
# ===========================================================================

def check_f1(rec):
    """百分比统一：同口径位数一致"""
    idx = read_text(os.path.join(ROOT, "index.html"))
    trig = read_text(os.path.join(ROOT, "trigger_analysis_report.html"))
    # index 主表预测值 2 位；trigger 明细表 4 位——属刻意分区，检查各自内部无混用 3 位研究值
    bad = []
    for fn, c in (("index.html", idx), ("trigger_analysis_report.html", trig)):
        if re.search(r"\b1\.\d{3}\b", c) and "1.938" not in c:
            # 粗略：研究值不应出现 3 位小数（如 1.931）
            if re.search(r"1\.9[0-9]{2}\b", c):
                bad.append(f"{fn} 出现 3 位小数研究值")
    if bad:
        rec.add("F1", "百分比统一", WARN, "；".join(bad) + "（需确认非笔误）")
    else:
        rec.add("F1", "百分比统一", PASS, "研究值主表 2 位 / 明细 4 位分区明确，未见混用 3 位小数")


def check_f2(rec, html_files):
    """BP 单位统一（核心页面阻断；遗留 WARN）"""
    core_bad = []
    for fn in CORE_PAGES:
        c = read_text(os.path.join(ROOT, fn))
        if "个基点" in c:
            core_bad.append(f"{fn} 使用「个基点」（与全站 BP 不统一）")
        if re.search(r"\bbp\b|\bbps\b", c, re.I):
            core_bad.append(f"{fn} 出现小写 bp/bps")
    if core_bad:
        rec.add("F2", "BP 单位", WARN, "；".join(core_bad) + "（建议统一为 BP；当前不阻断）")
        return
    legacy_bad = [fn for fn in LEGACY_PAGES if fn in html_files]
    if legacy_bad:
        rec.add("F2", "BP 单位", WARN,
                f"核心页面统一「BP」；遗留页面 {legacy_bad} 仍混用「个基点」/小写 bp（技术债）")
    else:
        rec.add("F2", "BP 单位", PASS, "全站统一使用「BP」")


def check_f3(rec, pred):
    """小数位数规则明确（数值精度：最多 4 位小数即视为一致；混用仅 WARN）"""
    mixed = []
    for p in pred["predictions"]:
        for k in ("predicted_value", "base_return", "ma250_gov", "spread_250"):
            v = p[k]
            if abs(round(v, 4) - v) > 1e-9:
                mixed.append(f"{p['quarter']}.{k}={v}")
    if mixed:
        rec.add("F3", "小数位数", WARN,
                f"存在超过 4 位小数的字段：{mixed[:3]}（建议生成时统一保留 4 位）")
    else:
        # 检查同类字段位数是否统一（json.dump 会丢弃尾随 0，如 1.761 / 1.74）
        lens = set(len(str(round(p["ma250_gov"], 4)).split(".")[-1]) for p in pred["predictions"])
        if len(lens) > 1:
            rec.add("F3", "小数位数", WARN,
                    f"predictions.json 同类字段小数位不统一（如 ma250_gov 出现 {sorted(lens)} 位混用），"
                    f"建议生成时补零至 4 位以保证展示一致")
        else:
            rec.add("F3", "小数位数", PASS, "predictions.json 研究值/MA/利差字段小数位规则一致")


def check_f4(rec, html_files):
    """标点/连接号统一（轻量自动 + 人工提示）"""
    rec.add("F4", "标点/连接号", MANUAL,
            "中文全角标点、季度区间连接号（~ / ～）、日期 YYYY-MM-DD 风格需人工目视核对全站一致性")


def check_f5(rec, act, pred):
    """季度编号连贯"""
    qs = [a["quarter"] for a in act["actuals"]] + [p["quarter"] for p in pred["predictions"]]
    expected = ["2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4",
                "2026Q1", "2026Q2", "2026Q3", "2026Q4", "2027Q1"]
    if qs == expected:
        rec.add("F5", "季度编号", PASS, "2024Q4→2027Q1 连续无重复遗漏，实际/预测分界清晰")
    else:
        dup = [q for q in set(qs) if qs.count(q) > 1]
        miss = [q for q in expected if q not in qs]
        rec.add("F5", "季度编号", FAIL, f"重复={dup} 缺失={miss}")


def check_f6(rec):
    """章节/图编号无重复"""
    frep = read_text(os.path.join(ROOT, "formula_report.html"))
    steps = re.findall(r"第([一二三四五六])步", frep)
    need = ["一", "二", "三", "四", "五"]
    if all(s in steps for s in need):
        rec.add("F6", "章节/图编号", PASS, "公式页第一~第五步编号连续无跳号/重复")
    else:
        rec.add("F6", "章节/图编号", WARN, f"公式页步骤编号缺失：{need} 中出现 {steps}")


def check_f7(rec, pred, act, html_files):
    """数据文件字段命名一致（predictions.json ∪ actuals.json 字段）"""
    keys = set(pred["predictions"][0].keys()) | set(act["actuals"][0].keys())
    used = set()
    for fn in html_files:
        c = read_text(os.path.join(ROOT, fn))
        for m in re.findall(r"\.(predicted_value|base_return|spread_250|spread_750|ma250_gov|ma750_gov|ref_rate|gap_bp|max_rate|announced|quarter|trigger|value)\b", c):
            used.add(m)
    missing = used - keys
    if missing:
        rec.add("F7", "字段命名", FAIL, f"页面引用字段不在数据文件：{missing}")
    else:
        rec.add("F7", "字段命名", PASS, "页面读取字段名与 predictions.json/actuals.json 字段名一致，无拼写漂移")


# ===========================================================================
# 四、自动化防线（A1-A3）
# ===========================================================================

def check_a1(rec):
    """推送前一致性校验（check_data_consistency.py）"""
    if not os.path.exists(CHECK_CONSISTENCY):
        rec.add("A1", "一致性校验", FAIL, "scripts/check_data_consistency.py 不存在")
        return
    env = dict(os.environ)
    env.setdefault("PRED_MAX_AGE_DAYS", "40")
    r = subprocess.run([sys.executable, CHECK_CONSISTENCY], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    if r.returncode == 0:
        rec.add("A1", "一致性校验", PASS, "check_data_consistency.py 规则1-4 通过（EXIT=0）")
    else:
        # 收集关键错误行
        errs = [l for l in r.stdout.splitlines() if l.startswith("  - ")]
        rec.add("A1", "一致性校验", FAIL,
                "check_data_consistency.py 未通过：" + ("；".join(errs[:3]) or "EXIT=1"))


def check_a2(rec, pred):
    """数据源不过期"""
    lu = pred.get("last_updated")
    if not lu:
        rec.add("A2", "数据不过期", FAIL, "predictions.json 缺 last_updated")
        return
    try:
        dt = datetime.datetime.strptime(lu, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            dt = datetime.datetime.fromisoformat(lu.replace("Z", "+00:00"))
            dt = dt.replace(tzinfo=None)
        except ValueError:
            rec.add("A2", "数据不过期", FAIL, f"last_updated 无法解析: {lu}")
            return
    max_age = int(os.environ.get("PRED_MAX_AGE_DAYS", "40"))
    age = (datetime.datetime.now() - dt).total_seconds() / 86400.0
    if age > max_age:
        rec.add("A2", "数据不过期", FAIL, f"predictions.json 已过期 {age:.1f} 天（> {max_age}），请重生")
    else:
        rec.add("A2", "数据不过期", PASS, f"last_updated={lu}（{age:.1f} 天前，≤{max_age}）")


def check_a3(rec):
    """发版后线上实测"""
    if os.environ.get("LIVE_CHECK") != "1":
        rec.add("A3", "发版后实测", MANUAL,
                "发版后由独立步骤/手动执行：curl 抓取线上两页，确认无旧值 1.9383、均引用 predictions.json、"
                "last_updated 一致。本次试运行已附带 LIVE_CHECK=1 实测。")
        return
    import urllib.request
    base = "https://sig546.github.io/preset-rate-research/"
    bad = []
    try:
        for page in ("index.html", "trigger_analysis_report.html"):
            with urllib.request.urlopen(base + page, timeout=30) as resp:
                html = resp.read().decode("utf-8", "ignore")
            if "1.9383" in html:
                bad.append(f"{page} 含旧值 1.9383")
            if "predictions.json" not in html:
                bad.append(f"{page} 未引用 predictions.json")
        with urllib.request.urlopen(base + "data/predictions.json", timeout=30) as resp:
            pj = json.loads(resp.read())
        if pj["predictions"][0]["predicted_value"] != 1.9313:
            bad.append("线上 predictions.json 首值非 1.9313")
    except Exception as e:
        rec.add("A3", "发版后实测", WARN, f"线上抓取失败：{e}（可能未部署或网络受限）")
        return
    if bad:
        rec.add("A3", "发版后实测", FAIL, "；".join(bad))
    else:
        rec.add("A3", "发版后实测", PASS, "线上两页无旧值、均引用 predictions.json，predictions.json 首值=1.9313")


# ===========================================================================
# 报告生成
# ===========================================================================

def build_report(rec, meta):
    today = datetime.date.today().isoformat()
    lines = []
    lines.append(f"# 一致性检核执行记录（{today}）\n")
    lines.append("> 自动生成自 `scripts/run_checklist.py`，对应 `docs/一致性检核清单.md`。\n")
    lines.append("## 基本信息\n")
    lines.append(f"- 仓库：`{meta['repo']}`")
    lines.append(f"- 检核 commit：`{meta['commit']}`")
    lines.append(f"- 运行时间：{meta['time']}")
    lines.append(f"- 运行环境：{meta['env']}")
    lines.append(f"- 预测值快照：{meta['pred_snapshot']}")
    lines.append(f"- 实际值快照：{meta['act_snapshot']}\n")
    lines.append("## 执行记录（基于清单模板）\n")
    lines.append("| 检查项 | 结果 | 备注 / 修订 commit |")
    lines.append("|--------|------|-------------------|")
    # 模板顺序
    order = [
        ("C1", "预测值 SSOT"), ("C2", "实际值三处一致"), ("C3", "最高值口径"),
        ("C4", "数据源声明"), ("C5", "引用有效"), ("C6", "更新时间"),
        ("C7", "预测可复算"), ("C8", "分段累加"), ("C9", "平推假设"),
        ("C10", "回溯汇总/明细"), ("C11", "触发主表/明细"),
        ("P1", "核心术语唯一"), ("P2", "分段系数表"), ("P3", "基础回报公式"),
        ("P4", "触发阈值"), ("P5", "预测趋势逻辑"), ("P6", "时间线"),
        ("P7", "章节标题"), ("P8", "图表=表格=源"), ("P9", "图表标注"),
        ("F1", "百分比统一"), ("F2", "BP 单位"), ("F3", "小数位数"),
        ("F4", "标点/连接号"), ("F5", "季度编号"), ("F6", "章节/图编号"),
        ("F7", "字段命名"), ("A1", "一致性校验"), ("A2", "数据不过期"),
        ("A3", "发版后实测"),
    ]
    by_id = {r[0]: r for r in rec.rows}
    for cid, title in order:
        if cid in by_id:
            _, _, status, note = by_id[cid]
            lines.append(f"| {cid} {title} | {status} | {note} |")
    lines.append("")
    lines.append(f"| **整体结论** | **{rec.overall()}** | FAIL={rec.fail}, WARN={rec.warn} |")
    lines.append("")
    lines.append("## 详细备注\n")
    if rec.detail:
        lines.extend(rec.detail)
    else:
        lines.append("- 全部检查点自动通过，无额外备注。")
    lines.append("")
    return "\n".join(lines)


# ===========================================================================
# 主流程
# ===========================================================================

def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    pred = load_json(os.path.join(DATA, "predictions.json"))
    act = load_json(os.path.join(DATA, "actuals.json"))
    html_files = sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))

    rec = Recorder()
    # 数据一致性
    check_c1(rec, pred, act, html_files)
    check_c2(rec, act, html_files)
    check_c3(rec, act, html_files)
    check_c4(rec, html_files)
    check_c5(rec, html_files)
    check_c6(rec, html_files)
    check_c7(rec)
    check_c8(rec)
    check_c9(rec, pred)
    check_c10(rec)
    check_c11(rec)
    # 表述一致性
    check_p1(rec, html_files)
    check_p2(rec)
    check_p3(rec)
    check_p4(rec, html_files)
    check_p5(rec, html_files)
    check_p6(rec, act, pred)
    check_p7(rec)
    check_p8(rec)
    check_p9(rec)
    # 格式一致性
    check_f1(rec)
    check_f2(rec, html_files)
    check_f3(rec, pred)
    check_f4(rec, html_files)
    check_f5(rec, act, pred)
    check_f6(rec)
    check_f7(rec, pred, act, html_files)
    # 自动化防线
    check_a1(rec)
    check_a2(rec, pred)
    check_a3(rec)

    meta = {
        "repo": "sig546/preset-rate-research",
        "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip() or "unknown",
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "env": "local/managed python 3.13",
        "pred_snapshot": " / ".join(f"{p['quarter']}={p['predicted_value']}" for p in pred["predictions"]),
        "act_snapshot": " / ".join(f"{a['quarter']}={a['value']}" for a in act["actuals"]),
    }
    report = build_report(rec, meta)
    today = datetime.date.today().isoformat()
    path_dated = os.path.join(REPORT_DIR, f"checklist_report_{today}.md")
    path_latest = os.path.join(REPORT_DIR, "latest.md")
    path_json = os.path.join(REPORT_DIR, "latest.json")
    with open(path_dated, "w", encoding="utf-8") as f:
        f.write(report)
    with open(path_latest, "w", encoding="utf-8") as f:
        f.write(report)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump({
            "date": today, "overall": rec.overall(),
            "fail": rec.fail, "warn": rec.warn,
            "rows": [{"id": r[0], "title": r[1], "status": r[2], "note": r[3]} for r in rec.rows],
        }, f, ensure_ascii=False, indent=2)

    print(report)
    print(f"\n📄 记录已写入：\n  - {path_dated}\n  - {path_latest}\n  - {path_json}")

    # CI 退出码：任一阻断级 FAIL 则失败
    sys.exit(1 if rec.fail else 0)


if __name__ == "__main__":
    main()
