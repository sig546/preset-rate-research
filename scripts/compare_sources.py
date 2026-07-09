#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只读对比：两套 cdb/ieb 数据源对预测研究值的影响
  方案A = 货币网近67条真实值 + 其余缺失日期用 Excel(中债) 补齐（混合口径）
  方案B = 中债估值 Excel 全量覆盖 cdb/ieb（全部中债口径）
  → 两套的长历史完全相同，唯一区别锁定在近67天（货币网 vs 中债），
    用以纯净地衡量"近期口径差异"对预测研究值的影响。
不修改任何数据文件，仅在内存中计算对比。
"""
import sys, json, copy, calendar
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import update_predictions as up

EXCEL = r"D:/05 工作/【00】预定利率研究值-excel版/data_国开债和进出口银行债 for workbuddy.xlsx"
MAX_RATE = 2.00  # 当前普通型最高值

# ── 载入基础数据 ──
bond = json.load(open(ROOT / "data" / "bond_yields.json", encoding="utf-8"))
data_raw = bond["data"]  # 原始：cdb/ieb 仅近67条货币网真实，其余 None
lpr = up.load_lpr_history()
dep = up.load_deposit_history()

# ── 载入 Excel 中债数据 ──
import openpyxl
wb = openpyxl.load_workbook(EXCEL, data_only=True)
ws = wb["Sheet1"]
xl = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    _, d, cdb, ieb = row
    if d is None:
        continue
    xl[d.strftime("%Y-%m-%d")] = (cdb, ieb)

# ── 方案A：近67条货币网真实值保留，其余缺失日期用 Excel(中债) 补齐（混合口径）──
data_A = copy.deepcopy(data_raw)
a_fill = 0  # 用 Excel 补齐的缺失天数
a_keep = 0  # 保留的货币网真实天数
for r in data_A:
    ds = r["date"]
    if r.get("cdb_10y") is not None:
        a_keep += 1
        continue  # 保留货币网真实值
    if ds in xl:
        c, i = xl[ds]
        if c is not None:
            r["cdb_10y"] = round(float(c), 4)
        if i is not None:
            r["ieb_10y"] = round(float(i), 4)
        a_fill += 1

# ── 方案B：全量用 Excel(中债) 覆盖 cdb/ieb（统一中债口径）──
data_B = copy.deepcopy(data_raw)
cov = 0
for r in data_B:
    ds = r["date"]
    if ds in xl:
        c, i = xl[ds]
        if c is not None:
            r["cdb_10y"] = round(float(c), 4)
        if i is not None:
            r["ieb_10y"] = round(float(i), 4)
        cov += 1

# 统计真实覆盖情况
a_cdb = sum(1 for r in data_A if r.get("cdb_10y") is not None)
b_cdb = sum(1 for r in data_B if r.get("cdb_10y") is not None)
print(f"方案A(混合): cdb/ieb 有值 {a_cdb} 条 = 货币网真实 {a_keep} + Excel补齐 {a_fill}")
print(f"方案B(全中债): cdb/ieb 有值 {b_cdb} 条（Excel覆盖 {cov} 天）")
print(f"gov_10y 总条数: {len(data_raw)}（两套相同）")
print(f"→ A与B唯一区别：近{a_keep}天用货币网(A) vs 中债(B)；长历史两套均为中债")
print("=" * 96)

# ── 预测季度 ──
quarters = up.get_prediction_quarters()

print(f"\n{'季度':<9}{'方案':<6}{'ref':>8}{'MA250':>8}{'MA750':>8}{'spr250':>9}{'spr750':>9}{'base':>8}{'预测%':>8}{'gap(BP)':>9}")
print("-" * 96)
rows_out = []
for q in quarters:
    cd = q["comp_date"]
    rA = up.compute_prediction(cd, data_A, lpr, dep)
    rB = up.compute_prediction(cd, data_B, lpr, dep)
    gapA = (MAX_RATE - rA["predicted"]) * 100
    gapB = (MAX_RATE - rB["predicted"]) * 100
    print(f"{q['quarter']:<9}{'A混合':<6}{rA['ref_rate']:>8.4f}{rA['ma250_gov']:>8.4f}{rA['ma750_gov']:>8.4f}"
          f"{rA['spread_250']:>9.4f}{rA['spread_750']:>9.4f}{rA['base_return']:>8.4f}{rA['predicted']:>8.4f}{gapA:>9.1f}")
    print(f"{'':<9}{'B全中债':<6}{rB['ref_rate']:>8.4f}{rB['ma250_gov']:>8.4f}{rB['ma750_gov']:>8.4f}"
          f"{rB['spread_250']:>9.4f}{rB['spread_750']:>9.4f}{rB['base_return']:>8.4f}{rB['predicted']:>8.4f}{gapB:>9.1f}")
    dpred = (rB["predicted"] - rA["predicted"]) * 100
    print(f"{'':<9}{'差异':<6}{'':>8}{'':>8}{'':>8}"
          f"{(rB['spread_250']-rA['spread_250'])*100:>8.2f}B{(rB['spread_750']-rA['spread_750'])*100:>8.2f}B"
          f"{(rB['base_return']-rA['base_return'])*100:>7.2f}B{dpred:>7.2f}B{(gapB-gapA):>8.1f}")
    print("-" * 96)
    rows_out.append((q["quarter"], rA, rB, dpred))

# ── 触发判断（连续2季 gap>=25BP）──
print("\n触发规则检查（gap = 最高值2.00% - 预测值；连续2季≥25BP触发下调）")
for label, key in [("方案A混合(近期货币网)", "A"), ("方案B全中债", "B")]:
    gaps = []
    for q, rA, rB, _ in rows_out:
        r = rA if key == "A" else rB
        gaps.append((MAX_RATE - r["predicted"]) * 100)
    trig = any(gaps[i] >= 25 and gaps[i+1] >= 25 for i in range(len(gaps)-1))
    print(f"  {label}: gap序列={[round(g,1) for g in gaps]} → {'⚠️触发' if trig else '不触发'}")
