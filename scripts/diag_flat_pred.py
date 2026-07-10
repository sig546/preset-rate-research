"""只读诊断：为何未来季度预测值完全相同。不修改任何文件。"""
import json, sys, calendar
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_predictions as up

ROOT = Path(__file__).resolve().parent.parent
bond = json.load(open(ROOT / "data" / "bond_yields.json", encoding="utf-8"))
bond_data = bond["data"]

# 1) 债券数据最后有 gov_10y 的日期
last_gov = max(r["date"] for r in bond_data if r.get("gov_10y") is not None)
print("债券数据最后有 gov_10y 的日期:", last_gov, "| 总条数:", len(bond_data))

# 2) 当前（未平推）逻辑下，4个季度的预测
quarters = up.get_prediction_quarters()
print("\n=== 当前逻辑（compute_ma 按 comp_date 截断，无平推）===")
print(f"{'季度':<9}{'comp_date':<12}{'ma250':>9}{'ma750':>9}{'spr250':>9}{'ref':>8}{'predicted':>11}")
for q in quarters:
    r = up.compute_prediction(q["comp_date"], bond_data)
    print(f"{q['quarter']:<9}{q['comp_date']:<12}{r['ma250_gov']:>9.4f}{r['ma750_gov']:>9.4f}{r['spread_250']:>9.4f}{r['ref_rate']:>8.2f}{r['predicted']:>11.4f}")
    n_gov = sum(1 for x in bond_data if x["date"] <= q["comp_date"] and x.get("gov_10y") is not None)
    print(f"          -> comp_date 之前 gov_10y 条数={n_gov} (均截至 {last_gov}, 因之后无数据)")

# 3) 模拟：对未来日期用最后一日值平推扩展，再算一次
print("\n=== 模拟：对未来日期做[平推]扩展后再算（参考 predict_future_corrected.extend_bond_data）===")
ext = []
for r in bond_data:
    ext.append(r)
# 拼接到 2027-03-31 的工作日平推
from datetime import date, timedelta
last_val = next(r["gov_10y"] for r in reversed(bond_data) if r.get("gov_10y") is not None)
last_cdb = next((r.get("cdb_10y") for r in reversed(bond_data) if r.get("cdb_10y") is not None), None)
last_ieb = next((r.get("ieb_10y") for r in reversed(bond_data) if r.get("ieb_10y") is not None), None)
d = date.fromisoformat(last_gov) + timedelta(days=1)
end = date(2027, 3, 31)
while d <= end:
    if d.weekday() < 5:
        ext.append({"date": d.isoformat(), "gov_10y": last_val,
                    "cdb_10y": last_cdb, "ieb_10y": last_ieb})
    d += timedelta(days=1)
print(f"平推后 bond 条数: {len(ext)} (新增 {len(ext)-len(bond_data)} 条常数平推)")
print(f"{'季度':<9}{'comp_date':<12}{'ma250':>9}{'ma750':>9}{'spr250':>9}{'predicted':>11}")
for q in quarters:
    r = up.compute_prediction(q["comp_date"], ext)
    print(f"{q['quarter']:<9}{q['comp_date']:<12}{r['ma250_gov']:>9.4f}{r['ma750_gov']:>9.4f}{r['spread_250']:>9.4f}{r['predicted']:>11.4f}")
