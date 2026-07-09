#!/usr/bin/env python3
"""
稳健版债券数据抓取（直接调用东方财富接口 + 子进程容错）
====================================================
- 10Y 国债(gov_10y): 直接分页调用东方财富 datacenter 接口，每页带超时、失败跳过
- 国开债(cdb_10y)/进出口债(ieb_10y): 尽力用 akshare 子进程抓取（中国货币网），失败则留 None
  即便缺失，原模型的税收溢价也有默认利差兜底，不影响预测主流程
"""
import json
import sys
import time
import multiprocessing as mp
from pathlib import Path
from datetime import datetime, date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BOND_FILE = DATA_DIR / "bond_yields.json"

CALL_TIMEOUT = 30
EM_URL = "https://datacenter.eastmoney.com/api/data/get"
EM_TOKEN = "894050c76af8597a853f5b408b759f5d"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://data.eastmoney.com/cjsj/zmgzsyl.html",
}
# 中美国债收益率报表列映射
COL_10Y = "EMM00166466"   # 中国国债收益率10年
COL_5Y = "EMM00166462"    # 中国国债收益率5年
COL_2Y = "EMM00588704"    # 中国国债收益率2年
COL_30Y = "EMM00166469"   # 中国国债收益率30年


def fetch_gov_direct():
    """直接分页抓取东方财富中美国债收益率，返回 [(date, gov10y), ...]"""
    import requests
    all_rows = []
    for p in range(1, 20):
        params = {
            "type": "RPTA_WEB_TREASURYYIELD", "sty": "ALL", "st": "SOLAR_DATE",
            "sr": "-1", "token": EM_TOKEN, "p": str(p), "ps": "500",
            "pageNo": str(p), "pageNum": str(p),
        }
        try:
            r = requests.get(EM_URL, params=params, timeout=15, headers=HEADERS)
            j = r.json()
            data = (j.get("result") or {}).get("data") or []
            if not data:
                break
            for row in data:
                d = row.get("SOLAR_DATE")
                v = row.get(COL_10Y)
                if d and v is not None:
                    try:
                        all_rows.append((str(d)[:10], float(v)))
                    except Exception:
                        pass
        except Exception as e:
            print(f"  [WARN] 国债第 {p} 页失败: {e}")
            continue
    all_rows.sort(key=lambda x: x[0])
    return all_rows


def _to_num(v):
    try:
        return float(v)
    except Exception:
        return None


def _worker_bulk(q, symbol, start, end):
    try:
        import akshare as ak
        df = ak.bond_china_close_return(symbol=symbol, period="1", start_date=start, end_date=end)
        df = df.rename(columns={"日期": "date", "到期收益率": "yield"})
        df["date"] = df["date"].astype(str)
        df["yield"] = df["yield"].apply(_to_num)
        if "期限" in df.columns:
            df["期限"] = df["期限"].apply(_to_num)
            df = df[df["期限"] == 10]
        recs = df[["date", "yield"]].dropna().to_dict("records")
        q.put(("ok", recs))
    except Exception as e:
        q.put(("err", str(e)[:400]))


def _run_in_process(target, timeout, *args):
    q = mp.Queue()
    p = mp.Process(target=target, args=(q, *args))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        try:
            p.kill()
        except Exception:
            pass
        p.join()
        return ("timeout", None)
    if not q.empty():
        return q.get()
    return ("empty", None)


def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print(f"稳健版债券数据抓取  {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 60)

    # ---- 国债（直接抓取，可靠）----
    print("[1/3] 抓取 10Y 国债收益率（东方财富直连）...")
    gov = fetch_gov_direct()
    if not gov:
        print("  [FAIL] 国债抓取失败")
        sys.exit(1)
    print(f"  国债: {len(gov)} 条")
    gov_dict = {d: v for d, v in gov}

    # ---- 国开债（批量，子进程容错）----
    print("[2/3] 抓取 10Y 国开债收益率（批量 2023~今）...")
    start = "20230101"
    end = date.today().strftime("%Y%m%d")
    status, cdb = _run_in_process(_worker_bulk, CALL_TIMEOUT, "政策性金融债(国开行)", start, end)
    if status == "ok" and cdb:
        cdb_dict = {r["date"]: r["yield"] for r in cdb}
        print(f"  国开债: {len(cdb_dict)} 条")
    else:
        print(f"  [WARN] 国开债抓取失败/为空（{status}），将留空")
        cdb_dict = {}

    # ---- 进出口债（批量，子进程容错）----
    print("[3/3] 抓取 10Y 进出口债收益率（批量 2023~今）...")
    status, ieb = _run_in_process(_worker_bulk, CALL_TIMEOUT, "政策性金融债(进出口行)", start, end)
    if status == "ok" and ieb:
        ieb_dict = {r["date"]: r["yield"] for r in ieb}
        print(f"  进出口债: {len(ieb_dict)} 条")
    else:
        print(f"  [WARN] 进出口债抓取失败/为空（{status}），将留空")
        ieb_dict = {}

    # ---- 合并 ----
    existing = load_json(BOND_FILE).get("data", [])
    existing_dates = {r["date"] for r in existing}
    all_dates = sorted(gov_dict.keys())
    new_entries = []
    for d in all_dates:
        if d in existing_dates:
            continue
        new_entries.append({
            "date": d,
            "gov_10y": round(float(gov_dict[d]), 4),
            "cdb_10y": round(float(cdb_dict[d]), 4) if d in cdb_dict else None,
            "ieb_10y": round(float(ieb_dict[d]), 4) if d in ieb_dict else None,
        })

    merged = {r["date"]: r for r in existing}
    for e in new_entries:
        merged[e["date"]] = e
    merged_list = sorted(merged.values(), key=lambda x: x["date"])

    save_json(BOND_FILE, {"data": merged_list, "last_updated": datetime.now().strftime("%Y-%m-%d")})

    with_cdb = sum(1 for r in merged_list if r.get("cdb_10y") is not None)
    with_ieb = sum(1 for r in merged_list if r.get("ieb_10y") is not None)
    print(f"\n[DONE] bond_yields.json 共 {len(merged_list)} 条")
    print(f"  含国开债: {with_cdb} 条 | 含进出口债: {with_ieb} 条")
    print(f"  日期范围: {merged_list[0]['date']} ~ {merged_list[-1]['date']}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
