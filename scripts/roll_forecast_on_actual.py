#!/usr/bin/env python3
"""
滚动预测窗口（当某个实际季度公布后调用）
====================================================
背景：update_actuals.py 只把新公布值追加到 actuals.json，并不触碰
predictions.json。于是已实现的季度（如 2026Q2）会同时出现在
actuals 与 predictions 两个文件里，导致一致性检核 P6/F5 阻断。

本脚本在「实际值已更新」之后调用：基于最新 actuals，用预测流水线
（离线、复用 update_predictions.py 的计算函数 + 本地债券/LPR/定存数据）
重新推导未来 4 个季度，写入 predictions.json，从而保证：
  - 每个季度恰好只出现一次（actuals=已公布，predictions=未来预测）
  - 与现网预测方法（分段累加 + 平推法）完全一致

用法：
  python scripts/roll_forecast_on_actual.py
  FORCE_UPDATE=true python scripts/roll_forecast_on_actual.py
"""
import json
import os
import sys
import importlib.util
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACT_FILE = ROOT / "data" / "actuals.json"
BOND_FILE = ROOT / "data" / "bond_yields.json"
PRED_FILE = ROOT / "data" / "predictions.json"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    force = os.environ.get("FORCE_UPDATE", "").lower() == "true"
    up = load_module("update_predictions", ROOT / "scripts" / "update_predictions.py")

    # 最新 actual 季度
    actuals = json.load(open(ACT_FILE, encoding="utf-8"))["actuals"]
    latest_actual = actuals[-1]["quarter"]
    print(f"[最新实际] {latest_actual} = {actuals[-1]['value']}%")

    # 离线读取本地债券 + LPR + 定存历史（不触网）
    bond = json.load(open(BOND_FILE, encoding="utf-8"))
    bond_list = bond.get("data", [])
    lpr_history = up.load_lpr_history()
    deposit_history = up.load_deposit_history()
    print(f"[债券] {len(bond_list)} 条 | LPR最新 {lpr_history[-1]} | 定存最新 {deposit_history[-1]}")

    # 推导未来 4 季度（基于最新 actual）
    quarters = up.get_prediction_quarters()
    print(f"[预测窗口] {[q['quarter'] for q in quarters]}")

    old = json.load(open(PRED_FILE, encoding="utf-8"))
    old_preds = old.get("predictions", [])
    old_by_q = {p["quarter"]: p for p in old_preds}

    new_preds = []
    for q in quarters:
        r = up.compute_prediction(q["comp_date"], bond_list, lpr_history, deposit_history)
        gap_bp = round((up.MAX_RATE - r["predicted"]) * 100, 1)
        entry = {
            "quarter": q["quarter"],
            "announced": q["announced"],
            "predicted_value": r["predicted"],
            "ref_rate": r["ref_rate"],
            "base_return": r["base_return"],
            "ma250_gov": r["ma250_gov"],
            "ma750_gov": r["ma750_gov"],
            "spread_250": r["spread_250"],
            "spread_750": r["spread_750"],
            "max_rate": up.MAX_RATE,
            "gap_bp": gap_bp,
            "trigger": gap_bp >= up.TRIGGER_THRESHOLD * 100,
        }
        new_preds.append(entry)
        tag = ""
        if q["quarter"] in old_by_q:
            delta = (r["predicted"] - old_by_q[q["quarter"]]["predicted_value"]) * 100
            tag = f"（对比旧值 {old_by_q[q['quarter']]['predicted_value']}: {delta:+.2f}BP）"
        print(f"  {q['quarter']}: {r['predicted']:.4f}%  差值 {gap_bp}BP  {'触发' if entry['trigger'] else '未触发'} {tag}")

    # 校验：与旧值比对是否在合理变动范围内
    warnings = up.validate_predictions(new_preds, old_preds)
    for w in warnings:
        print("  ⚠️", w)

    # 写回（保留 base_data / method / description）
    out = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "method": old.get("method", "平推法（未来债券收益率/LPR/定存均维持当前水平不变）"),
        "description": old.get("description", "普通型人身保险产品预定利率研究值 — 未来4季度模型预测（平推法）"),
        "base_data": old.get("base_data", {
            "lpr_5y": up.get_lpr_for_month(2026, 7, lpr_history),
            "deposit_5y": up.get_deposit_for_month(2026, 7, deposit_history),
            "bond_yield_10y": bond_list[-1]["gov_10y"],
        }),
        "predictions": new_preds,
        "validation_warnings": warnings,
    }
    json.dump(out, open(PRED_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[DONE] 已写回 {PRED_FILE}（移除已实现的 {latest_actual} 预测，滚动至 {new_preds[-1]['quarter']}）")


if __name__ == "__main__":
    main()
