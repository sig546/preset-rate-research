#!/usr/bin/env python3
"""
补充国开债/进出口债 10Y 收益率到 bond_yields.json（修正版）
====================================================
根因：akshare 的 bond_china_close_return 把国开债标签错写成
"政策性金融债(国开行)"，与货币网真实标签"政策性金融债(国开)"(CYCC021)不符导致整列缺失。
本脚本用正确代码直连中国货币网 ClsYldCurvHis：
  - 国开债 10Y: CYCC021
  - 进出口债 10Y: CYCC024
要点：
  - 期限字段 yearTermStr 为浮点字符串（如 "10.0"），用 abs(float-10)<0.01 匹配 10Y
  - pageSize 必须 <=50（>=200 会 403 被反爬拦截）；每页约含 4 个交易日
  - 按月分页抓取，带 403/JSON 解析失败的退避重试
"""
import json
import time
import calendar
import requests
from pathlib import Path
from datetime import datetime, date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOND_FILE = PROJECT_ROOT / "data" / "bond_yields.json"

URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/ClsYldCurvHis"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.chinamoney.com.cn/chinese/bkcurvclosedyhis/?bondType=CYCC021&reference=1",
    "X-Requested-With": "XMLHttpRequest",
}

BOND_TYPES = {
    "cdb_10y": "CYCC021",   # 政策性金融债(国开)
    "ieb_10y": "CYCC024",   # 政策性金融债(进出口行)
}


def _is_10y(term_str):
    try:
        return abs(float(term_str) - 10.0) < 0.01
    except Exception:
        return False


def fetch_10y(bond_type_code, start_ym, end_ym):
    result = {}
    y0, m0 = start_ym
    y1, m1 = end_ym
    total_months = (y1 - y0) * 12 + (m1 - m0) + 1
    for i in range(total_months):
        yy = y0 + (m0 + i - 1) // 12
        mm = (m0 + i - 1) % 12 + 1
        sd = f"{yy}{mm:02d}01"
        ed = f"{yy}{mm:02d}{calendar.monthrange(yy, mm)[1]}"
        page = 1
        while True:
            params = {
                "lang": "CN", "reference": "1,2,3", "bondType": bond_type_code,
                "startDate": sd, "endDate": ed, "termId": "10",
                "pageNum": str(page), "pageSize": "50",
            }
            ok = False
            for attempt in range(4):
                try:
                    r = requests.get(URL, headers=HEADERS, params=params, timeout=20)
                    if r.status_code == 403:
                        raise requests.HTTPError("403")
                    recs = (r.json().get("records") or [])
                    ok = True
                    break
                except Exception:
                    wait = 2 * (attempt + 1)
                    time.sleep(wait)
            if not ok:
                print(f"    [{bond_type_code}] {yy}-{mm:02d} p{page} 多次重试仍失败，跳过")
                break
            for rec in recs:
                if _is_10y(rec.get("yearTermStr", "")):
                    d = rec.get("newDateValueCN")
                    yv = rec.get("maturityYieldStr")
                    if d and yv not in (None, "---", ""):
                        try:
                            result[d] = float(yv)
                        except Exception:
                            pass
            if len(recs) < 50:
                break
            page += 1
            time.sleep(0.25)
    return result


def main():
    print("=" * 60)
    print(f"补充国开债/进出口债 10Y 收益率（修正版）  {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 60)

    with open(BOND_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("data", [])
    idx = {r["date"]: r for r in rows}

    start_ym = (2023, 1)
    end_ym = (date.today().year, date.today().month)

    for field, code in BOND_TYPES.items():
        print(f"\n[{field}] 抓取 {code} (2023-01 ~ {end_ym[0]}-{end_ym[1]:02d}) ...")
        vals = fetch_10y(code, start_ym, end_ym)
        print(f"  接口返回 {len(vals)} 条 10Y")
        matched = 0
        for d, v in vals.items():
            if d in idx:
                idx[d][field] = round(v, 4)
                matched += 1
        print(f"  匹配写入现有记录 {matched} 条")
        if vals:
            last_d = max(vals.keys())
            print(f"  样例: {last_d} -> {vals[last_d]}%")

    with open(BOND_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    cdb = sum(1 for r in rows if r.get("cdb_10y") is not None)
    ieb = sum(1 for r in rows if r.get("ieb_10y") is not None)
    print(f"\n[DONE] bond_yields.json: cdb_10y 有 {cdb} 条, ieb_10y 有 {ieb} 条 (共 {len(rows)} 条)")


if __name__ == "__main__":
    main()
