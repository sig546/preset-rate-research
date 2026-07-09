# -*- coding: utf-8 -*-
"""
合并补齐 bond_yields.json 的 cdb_10y / ieb_10y 两列。

数据源策略（经用户确认）：
  - 近 67 天（2026-04-01 ~ 2026-07-08）：保留已抓取的【中国货币网】真实值，不动。
  - 其余历史日期：用【中债估值 Excel】补齐。
  - 后续：由 GitHub Actions 按月抓取货币网数据做增量累积。

Excel 单位为 %（如 1.7855 表示 1.7855%），与 json 现有格式一致。
运行前请确保已备份 data/bond_yields.json。
"""
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "bond_yields.json"
EXCEL = r"D:/05 工作/【00】预定利率研究值-excel版/data_国开债和进出口银行债 for workbuddy.xlsx"

# 近期货币网真实值窗口（这段保留货币网，不用 Excel 覆盖）
CNY_START = "2026-04-01"
CNY_END = "2026-07-08"


def load_excel():
    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Sheet1"]
    xl = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        _, d, cdb, ieb = row
        if d is None:
            continue
        ds = d.strftime("%Y-%m-%d")
        c = round(float(cdb), 4) if cdb is not None else None
        i = round(float(ieb), 4) if ieb is not None else None
        xl[ds] = (c, i)
    return xl


def main():
    d = json.load(open(JSON_PATH, encoding="utf-8"))
    data = d["data"]
    xl = load_excel()

    kept_cny = 0      # 保留货币网的天数
    filled_excel = 0  # 用 Excel 补齐的天数
    no_source = 0     # 既非货币网窗口、Excel 也无值

    for r in data:
        ds = r["date"]
        in_cny = CNY_START <= ds <= CNY_END
        has_cny = r.get("cdb_10y") is not None or r.get("ieb_10y") is not None

        if in_cny and has_cny:
            # 近期货币网真实值，保留
            kept_cny += 1
            continue

        # 其余日期：用 Excel 补齐
        if ds in xl:
            c, i = xl[ds]
            if c is not None:
                r["cdb_10y"] = c
            if i is not None:
                r["ieb_10y"] = i
            filled_excel += 1
        else:
            no_source += 1

    # 写回（保持缩进与非 ASCII 原样）
    d["last_updated"] = d.get("last_updated")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    # 校验
    cdb_cnt = sum(1 for r in data if r.get("cdb_10y") is not None)
    ieb_cnt = sum(1 for r in data if r.get("ieb_10y") is not None)
    cdb_dates = [r["date"] for r in data if r.get("cdb_10y") is not None]
    ieb_dates = [r["date"] for r in data if r.get("ieb_10y") is not None]

    print("=== 合并完成 ===")
    print(f"总条数: {len(data)}")
    print(f"保留货币网(近期): {kept_cny} 天")
    print(f"Excel 中债补齐: {filled_excel} 天")
    print(f"无任何来源(缺口): {no_source} 天")
    print("-" * 50)
    print(f"cdb_10y 有值: {cdb_cnt} 条  范围: {cdb_dates[0]} ~ {cdb_dates[-1]}")
    print(f"ieb_10y 有值: {ieb_cnt} 条  范围: {ieb_dates[0]} ~ {ieb_dates[-1]}")
    # 抽样
    print("-" * 50)
    print("抽样(最早3条 + 边界 + 最新3条):")
    show = data[:3]
    # 找边界 2026-03-31 与 2026-04-01
    for r in data:
        if r["date"] in ("2026-03-31", "2026-04-01"):
            show.append(r)
    show += data[-3:]
    for r in show:
        print("  ", r)


if __name__ == "__main__":
    main()
