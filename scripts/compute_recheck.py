"""只读：用最新 bond_yields.json 计算未来4季度预测值（含平推扩展修复），仅打印不写文件。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_predictions as up

ROOT = Path(__file__).resolve().parent.parent
bond = json.load(open(ROOT / "data" / "bond_yields.json", encoding="utf-8"))
bond_data = bond["data"]

last_gov = max(r["date"] for r in bond_data if r.get("gov_10y") is not None)
print("债券数据最后有 gov_10y 的日期:", last_gov, "| 总条数:", len(bond_data))
print(f"\n{'季度':<9}{'comp_date':<12}{'ma250':>9}{'ma750':>9}{'spr250':>9}{'ref':>8}{'基础回报':>11}{'预测值':>11}{'差值BP':>8}")
print("-" * 86)

quarters = up.get_prediction_quarters()
results = []
for q in quarters:
    r = up.compute_prediction(q["comp_date"], bond_data)
    gap = round((up.MAX_RATE - r["predicted"]) * 100, 1)
    trig = "⚠触发" if gap >= up.TRIGGER_THRESHOLD * 100 else "不触发"
    print(f"{q['quarter']:<9}{q['comp_date']:<12}{r['ma250_gov']:>9.4f}{r['ma750_gov']:>9.4f}{r['spread_250']:>9.4f}{r['ref_rate']:>8.2f}{r['base_return']:>11.4f}{r['predicted']:>11.4f}{gap:>8.1f} {trig}")
    results.append((q["quarter"], r["predicted"]))

print("\n（修复前 Q3/Q4/Q1 均为 1.9323，完全一样；修复后如上应出现渐变）")
