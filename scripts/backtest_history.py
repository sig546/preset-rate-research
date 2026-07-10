#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史值回溯测试 (Backtest)
====================================================
基于【当前部署公式】对已经公布的实际研究值做回溯：
  - 债券数据：data/bond_yields.json（6122 条，gov/cdb/ieb 真实值，动态税收溢价）
  - LPR / 定存：data/lpr_history.json / deposit_rates.json
  - 实际值：data/actuals.json

对同一批历史季度，分别用两种分段系数实现：
  - Model A：当前部署公式（update_predictions.apply_segment，整值乘系数）
  - Model B：分段累加实现（public_data_calculation.calculate_coeff）

输出：控制台对比表 + backtest_history.json + backtest_report.html
"""

import json
import calendar
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ── 分段系数 ──
# Model A（部署脚本）：2.50~3.00 段系数 1.00，整值乘系数
SEGMENT_A = [
    (0.00, 1.00, 1.00), (1.00, 2.00, 1.00), (2.00, 2.50, 0.95),
    (2.50, 3.00, 1.00), (3.00, 3.50, 0.50), (3.50, 4.00, 0.50), (4.00, 10.00, 0.30),
]
# Model B（分段累加实现）：2.50~3.00 段系数 0.95
SEGMENT_B = [
    (0.00, 1.00, 1.00), (1.00, 2.00, 1.00), (2.00, 2.50, 0.95),
    (2.50, 3.00, 0.95), (3.00, 3.50, 0.50), (3.50, 4.00, 0.50), (4.00, 10.00, 0.30),
]


def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_lpr_for_month(year, month, lpr_history):
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    rate = lpr_history[0][1]
    for d, r in lpr_history:
        if date.fromisoformat(d) <= month_end:
            rate = r
    return rate


def get_deposit_for_month(year, month, deposit_history):
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    rate = deposit_history[0][1]
    for d, r in deposit_history:
        if date.fromisoformat(d) <= month_end:
            rate = r
    return rate


def compute_ma(bond_data, comp_date, window, field):
    cutoff = comp_date
    values = [r[field] for r in bond_data if r["date"] <= cutoff and r.get(field) is not None]
    if not values:
        return None
    n = min(window, len(values))
    return sum(values[-n:]) / n


def compute_spread_ma(bond_data, comp_date, window):
    cutoff = comp_date
    eligible = [r for r in bond_data if r["date"] <= cutoff]
    spreads = []
    for r in eligible[-window:]:
        s1 = r["cdb_10y"] - r["gov_10y"] if (r.get("cdb_10y") is not None and r.get("gov_10y") is not None) else None
        s2 = r["ieb_10y"] - r["gov_10y"] if (r.get("ieb_10y") is not None and r.get("gov_10y") is not None) else None
        if s1 is not None or s2 is not None:
            spreads.append(max(s1 if s1 is not None else -99, s2 if s2 is not None else -99))
    if not spreads:
        return 0.0912
    return sum(spreads) / len(spreads)


def apply_segment(pre, segs):
    for low, high, coeff in segs:
        if low < pre <= high:
            return pre * coeff
    return pre


def calc_cumulative(pre, segs):
    total = 0.0
    for low, high, coeff in segs:
        if pre > high:
            total += (high - low) * coeff
        elif pre > low:
            total += (pre - low) * coeff
        else:
            break
    return total


def compute_prediction(comp_date, bond_data, lpr_history, deposit_history, mode):
    comp_dt = date.fromisoformat(comp_date)
    # 参考利率：6 个月 (LPR+定存)/2 均值（截至 comp 月）
    ref_rates = []
    for i in range(5, -1, -1):
        y, m = comp_dt.year, comp_dt.month - i
        while m <= 0:
            y -= 1
            m += 12
        ref_rates.append((get_lpr_for_month(y, m, lpr_history) + get_deposit_for_month(y, m, deposit_history)) / 2)
    ref_rate = sum(ref_rates) / len(ref_rates)

    ma250 = compute_ma(bond_data, comp_date, 250, "gov_10y")
    ma750 = compute_ma(bond_data, comp_date, 750, "gov_10y")
    sp250 = compute_spread_ma(bond_data, comp_date, 250)
    sp750 = compute_spread_ma(bond_data, comp_date, 750)

    base_250 = ma250 + sp250
    base_750 = ma750 + sp750
    base_return = min(base_250, base_750)
    pre_adj = min(ref_rate, base_return)

    segs = SEGMENT_A if mode == "A" else SEGMENT_B
    if mode == "A":
        predicted = apply_segment(pre_adj, segs)
    else:
        predicted = calc_cumulative(pre_adj, segs)

    return {
        "ref_rate": ref_rate,
        "ma250_gov": ma250,
        "ma750_gov": ma750,
        "spread_250": sp250,
        "spread_750": sp750,
        "base_return": base_return,
        "pre_adj": pre_adj,
        "predicted": predicted,
    }


def comp_date_for(quarter):
    y = int(quarter[:4])
    q = int(quarter[5:])
    month = {1: 3, 2: 6, 3: 9, 4: 12}[q]
    return f"{y}-{month:02d}-{calendar.monthrange(y, month)[1]}"


def main():
    bond_data = load_json(DATA_DIR / "bond_yields.json").get("data", [])
    lpr_history = [(e["date"], e["rate"]) for e in load_json(DATA_DIR / "lpr_history.json").get("history", [])]
    deposit_history = [(e["date"], e["rate"]) for e in load_json(DATA_DIR / "deposit_rates.json").get("history", [])]
    actuals = load_json(DATA_DIR / "actuals.json").get("actuals", [])

    print(f"债券数据：{len(bond_data)} 条，范围 {bond_data[0]['date']} ~ {bond_data[-1]['date']}")
    print(f"LPR 记录：{len(lpr_history)} 条；定存记录：{len(deposit_history)} 条；实际值：{len(actuals)} 条\n")

    rows = []
    for a in actuals:
        q = a["quarter"]
        actual = a["value"]
        comp = comp_date_for(q)
        rA = compute_prediction(comp, bond_data, lpr_history, deposit_history, "A")
        rB = compute_prediction(comp, bond_data, lpr_history, deposit_history, "B")
        diffA = (rA["predicted"] - actual) * 100
        diffB = (rB["predicted"] - actual) * 100
        rows.append({
            "quarter": q, "comp_date": comp, "actual": actual,
            "pred_A": rA["predicted"], "diff_A_bp": diffA,
            "pred_B": rB["predicted"], "diff_B_bp": diffB,
            "ref_rate": rA["ref_rate"], "base_return": rA["base_return"],
            "ma250_gov": rA["ma250_gov"], "ma750_gov": rA["ma750_gov"],
            "spread_250": rA["spread_250"], "spread_750": rA["spread_750"],
            "pre_adj": rA["pre_adj"],
        })

    # 控制台表格
    print(f"{'季度':<8}{'计算日':<12}{'实际值':>8}{'模型A':>9}{'差(A)BP':>9}{'模型B':>9}{'差(B)BP':>9}")
    print("-" * 72)
    sumA = sumB = maxA = maxB = 0.0
    for r in rows:
        dA = r["diff_A_bp"]; dB = r["diff_B_bp"]
        sumA += abs(dA); sumB += abs(dB)
        maxA = max(maxA, abs(dA)); maxB = max(maxB, abs(dB))
        print(f"{r['quarter']:<8}{r['comp_date']:<12}{r['actual']:>8.2f}{r['pred_A']:>9.2f}{dA:>9.1f}{r['pred_B']:>9.2f}{dB:>9.1f}")
    n = len(rows)
    print("-" * 72)
    print(f"{'均值|差|':<20}{'':>20}{sumA/n:>9.2f}{'':>9}{sumB/n:>9.2f}")
    print(f"{'最大|差|':<20}{'':>20}{maxA:>9.2f}{'':>9}{maxB:>9.2f}")
    print("\n（差=模型-实际，正=模型偏高；单位 BP）")

    # 保存 JSON
    out = {
        "description": "历史值回溯测试（基于当前数据 + 当前部署公式）",
        "bond_range": [bond_data[0]["date"], bond_data[-1]["date"]],
        "rows": rows,
        "summary": {
            "n": n,
            "mean_abs_diff_A_bp": round(sumA / n, 2),
            "max_abs_diff_A_bp": round(maxA, 2),
            "mean_abs_diff_B_bp": round(sumB / n, 2),
            "max_abs_diff_B_bp": round(maxB, 2),
        },
    }
    out_path = DATA_DIR / "backtest_history.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[保存] {out_path}")

    # HTML 报告
    write_html(rows, out["summary"], out_path.parent)


def write_html(rows, summary, data_dir):
    labels = [r["quarter"] for r in rows]
    actual = [round(r["actual"], 2) for r in rows]
    predA = [round(r["pred_A"], 2) for r in rows]
    predB = [round(r["pred_B"], 2) for r in rows]
    diffA = [round(r["diff_A_bp"], 1) for r in rows]

    trs = ""
    for r in rows:
        dA = r["diff_A_bp"]
        cls = "ok" if abs(dA) < 5 else ("warn" if abs(dA) < 10 else "bad")
        trs += (
            f"<tr><td>{r['quarter']}</td><td>{r['comp_date']}</td>"
            f"<td class='num'>{r['actual']:.2f}</td>"
            f"<td class='num'>{r['pred_A']:.2f}</td>"
            f"<td class='num {cls}'>{dA:+.1f}</td>"
            f"<td class='num'>{r['pred_B']:.2f}</td>"
            f"<td class='num {cls}'>{r['diff_B_bp']:+.1f}</td>"
            f"<td class='num'>{r['ref_rate']:.2f}</td>"
            f"<td class='num'>{r['base_return']:.2f}</td>"
            f"<td class='num'>{r['ma250_gov']:.2f}</td>"
            f"<td class='num'>{r['ma750_gov']:.2f}</td>"
            f"<td class='num'>{r['spread_250']:.2f}</td>"
            f"<td class='num'>{r['spread_750']:.2f}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>预定利率研究值 · 历史回溯</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
 body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:24px;color:#1f2329;background:#fff;}}
 h1{{font-size:22px;margin-bottom:4px;}} .sub{{color:#8a9099;font-size:13px;margin-bottom:18px;}}
 .cards{{display:flex;gap:14px;margin:18px 0;flex-wrap:wrap;}}
 .card{{flex:1;min-width:160px;border:1px solid #e5e6eb;border-radius:10px;padding:14px 16px;background:#fafbfc;}}
 .card .k{{font-size:12px;color:#8a9099;}} .card .v{{font-size:24px;font-weight:700;margin-top:4px;}}
 table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:10px;}}
 th,td{{border:1px solid #e5e6eb;padding:7px 9px;text-align:center;}}
 th{{background:#f2f3f5;}} td.num{{font-variant-numeric:tabular-nums;}}
 tr.ok td:nth-child(5),tr.ok td:nth-child(7){{color:#1f9d55;}}
 tr.warn td:nth-child(5),tr.warn td:nth-child(7){{color:#d48806;}}
 tr.bad td:nth-child(5),tr.bad td:nth-child(7){{color:#d4380d;font-weight:700;}}
 .chart-box{{max-width:760px;margin:22px 0;}}
 .note{{font-size:12px;color:#8a9099;line-height:1.6;margin-top:14px;}}
</style></head><body>
<h1>预定利率研究值 · 历史回溯测试</h1>
<div class="sub">基于当前数据（真实债券收益率 + 动态税收溢价）对 6 个已公布季度做回溯，对比模型输出与实际值。差 = 模型 − 实际（BP）。</div>
<div class="cards">
 <div class="card"><div class="k">模型A 平均|差|</div><div class="v">{summary['mean_abs_diff_A_bp']:.2f}<span style="font-size:13px"> BP</span></div></div>
 <div class="card"><div class="k">模型A 最大|差|</div><div class="v">{summary['max_abs_diff_A_bp']:.2f}<span style="font-size:13px"> BP</span></div></div>
 <div class="card"><div class="k">模型B 平均|差|</div><div class="v">{summary['mean_abs_diff_B_bp']:.2f}<span style="font-size:13px"> BP</span></div></div>
 <div class="card"><div class="k">模型B 最大|差|</div><div class="v">{summary['max_abs_diff_B_bp']:.2f}<span style="font-size:13px"> BP</span></div></div>
</div>
<div class="chart-box"><canvas id="c1"></canvas></div>
<table>
<tr><th>季度</th><th>计算日</th><th>实际值%</th><th>模型A%</th><th>差A(BP)</th><th>模型B%</th><th>差B(BP)</th><th>参考利率%</th><th>基础回报%</th><th>MA250国债%</th><th>MA750国债%</th><th>利差250%</th><th>利差750%</th></tr>
{trs}
</table>
<div class="note">
模型A = 当前部署公式（update_predictions.apply_segment，整值乘分段系数；2.50~3.00 段系数 1.00）。<br>
模型B = 分段累加实现（public_data_calculation.calculate_coeff；2.50~3.00 段系数 0.95）。<br>
税收溢价 = max(国开−国债, 进出口−国债) 的 250/750 日移动平均（由 bond_yields.json 真实数据动态计算）。<br>
计算日 = 各季度末（与实际公布时点一致）。参考利率窗口为计算日前 6 个月。
</div>
<script>
new Chart(document.getElementById('c1'),{{
 type:'bar',
 data:{{ labels:{labels},
   datasets:[
     {{label:'实际值',data:{actual},backgroundColor:'#5b8ff9'}},
     {{label:'模型A',data:{predA},backgroundColor:'#5ad8a6'}},
     {{label:'模型B',data:{predB},backgroundColor:'#f6bd16'}}
   ]}},
 options:{{plugins:{{title:{{display:true,text:'实际值 vs 模型A/B 回溯对比 (%)'}}}},
   scales:{{y:{{title:{{display:true,text:'预定利率研究值 (%)'}}}}}}}}
}});
</script>
</body></html>"""
    html_path = data_dir / "backtest_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[保存] {html_path}")


if __name__ == "__main__":
    main()
