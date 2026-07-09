#!/usr/bin/env python3
"""
预定利率研究值 — 预测值自动更新脚本
====================================================
触发条件（脚本内部判断）：
  1. 本月首个工作日（排除周末+中国法定节假日）
  2. 本月末个工作日
  3. actuals.json 的 last_updated 是今天

数据来源：akshare（国债/国开债/进出口行债日频收益率）
方法：平推法（flat-forward）
"""

import json, re, os, sys, calendar, time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
BOND_FILE = DATA_DIR / "bond_yields.json"
ACTUALS_FILE = DATA_DIR / "actuals.json"
PREDICTIONS_FILE = DATA_DIR / "predictions.json"
LPR_FILE = DATA_DIR / "lpr_history.json"
DEPOSIT_FILE = DATA_DIR / "deposit_rates.json"

# ── LPR 自动获取 ──
def fetch_lpr_from_akshare() -> list:
    """通过 akshare 获取5年期LPR完整历史，返回 [(date_str, rate), ...]"""
    import akshare as ak
    try:
        df = ak.macro_china_lpr()
        # 筛选5年期LPR，按日期排序
        if "期限" in df.columns:
            df = df[df["期限"].str.contains("5", na=False)]
        df = df.sort_values("TRADE_DATE" if "TRADE_DATE" in df.columns else df.columns[0])
        date_col = "TRADE_DATE" if "TRADE_DATE" in df.columns else df.columns[0]
        rate_col = "LPR" if "LPR" in df.columns else [c for c in df.columns if "LPR" in str(c) or "利率" in str(c)][0]
        history = []
        for _, row in df.iterrows():
            d = str(row[date_col])[:10]
            r = float(row[rate_col])
            if r > 0:  # 过滤无效值
                history.append((d, r))
        # 只保留利率变动的日期
        result = []
        last_rate = None
        for d, r in history:
            if r != last_rate:
                result.append((d, r))
                last_rate = r
        return result
    except Exception as e:
        print(f"  [WARN] LPR获取失败: {e}，使用默认值")
        return [
            ("2023-06-20", 4.20), ("2024-02-20", 3.95),
            ("2024-07-22", 3.85), ("2024-10-21", 3.60), ("2025-05-20", 3.50),
        ]

def load_lpr_history() -> list:
    """加载或获取LPR历史数据"""
    if LPR_FILE.exists():
        with open(LPR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        stored = [(e["date"], e["rate"]) for e in data.get("history", [])]
        if stored:
            return stored
    # 首次获取
    history = fetch_lpr_from_akshare()
    save_json(LPR_FILE, {"last_updated": datetime.now().strftime("%Y-%m-%d"), "history": [{"date": d, "rate": r} for d, r in history]})
    return history

def get_lpr_for_month(year: int, month: int, lpr_history: list = None) -> float:
    """获取指定月份适用的5年期LPR"""
    if lpr_history is None:
        lpr_history = load_lpr_history()
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    rate = lpr_history[0][1] if lpr_history else 3.50
    for d, r in lpr_history:
        if date.fromisoformat(d) <= month_end:
            rate = r
    return rate

# ── 定存利率（JSON存储 + 新闻监测追加） ──
DEPOSIT_DEFAULTS = [
    ("2023-12-22", 2.00), ("2024-07-25", 1.80),
    ("2024-10-18", 1.55), ("2025-05-20", 1.30),
]

def load_deposit_history() -> list:
    """加载定存利率历史数据"""
    if DEPOSIT_FILE.exists():
        with open(DEPOSIT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        stored = [(e["date"], e["rate"]) for e in data.get("history", [])]
        if stored:
            return stored
    # 初始化
    save_json(DEPOSIT_FILE, {"last_updated": datetime.now().strftime("%Y-%m-%d"), "history": [{"date": d, "rate": r} for d, r in DEPOSIT_DEFAULTS]})
    return DEPOSIT_DEFAULTS

def check_deposit_rate_news() -> bool:
    """搜索'六大行 下调 存款利率'新闻，检测新调整。返回是否有更新。"""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text("六大行 下调 存款利率", max_results=5):
                results.append({"title": r.get("title", ""), "body": r.get("body", ""), "href": r.get("href", "")})
    except Exception:
        try:
            # 备用：新华网搜索
            import urllib.request, urllib.parse
            keyword = urllib.parse.quote("国有大行 下调 存款利率")
            url = f"https://so.news.cn/getNews?keyword={keyword}&curPage=1&sortField=0&searchFields=1&lang=cn"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                results = [{"title": item.get("title", ""), "body": item.get("description", ""), "href": item.get("url", "")}
                          for item in data.get("content", {}).get("results", [])]
        except Exception:
            return False

    if not results:
        return False

    # 正则匹配：X.XX% 五年期 / 5年期 / 五年定存
    rate_pat = re.compile(r"(\d+\.\d+)\s*%.*?(?:五年|5年)")
    date_pat = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")

    for r in results:
        text = r["title"] + " " + r["body"]
        rate_m = rate_pat.search(text)
        date_m = date_pat.search(text)
        if rate_m and date_m:
            new_rate = float(rate_m.group(1))
            new_date = f"{date_m.group(1)}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}"

            # 检查是否已存在
            existing = load_deposit_history()
            known_dates = {d for d, _ in existing}
            if new_date not in known_dates and 1.0 <= new_rate <= 2.5:
                # 追加
                current = load_json(DEPOSIT_FILE) if DEPOSIT_FILE.exists() else {}
                if "history" not in current:
                    current["history"] = [{"date": d, "rate": r} for d, r in DEPOSIT_DEFAULTS]
                current["history"].append({"date": new_date, "rate": new_rate, "source": r["href"]})
                current["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                save_json(DEPOSIT_FILE, current)
                print(f"  [定存] 发现新调整: {new_date} → {new_rate}%")
                return True
    return False

def get_deposit_for_month(year: int, month: int, deposit_history: list = None) -> float:
    """获取指定月份适用的5年期定存利率"""
    if deposit_history is None:
        deposit_history = load_deposit_history()
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    rate = deposit_history[0][1] if deposit_history else 1.30
    for d, r in deposit_history:
        if date.fromisoformat(d) <= month_end:
            rate = r
    return rate
SEGMENT_COEFF = [
    (0.00, 1.00, 1.00), (1.00, 2.00, 1.00), (2.00, 2.50, 0.95),
    (2.50, 3.00, 1.00), (3.00, 3.50, 0.50),
    (3.50, 4.00, 0.50), (4.00, 10.00, 0.30),
]
MAX_RATE = 2.00  # 当前普通型预定利率最高值
TRIGGER_THRESHOLD = 0.25
VALIDATION_MAX_CHANGE_BP = 50  # 预测值相邻变化阈值（BP，告警不阻止）

# ── 工作日判断（含中国法定节假日） ──
def is_workday(d: date) -> bool:
    try:
        from chinese_calendar import is_workday as c_is_workday
        return c_is_workday(d)
    except ImportError:
        return d.weekday() < 5

def is_first_working_day() -> bool:
    today = date.today()
    d = date(today.year, today.month, 1)
    while not is_workday(d):
        d += timedelta(days=1)
    return today == d

def is_last_working_day() -> bool:
    today = date.today()
    last_num = calendar.monthrange(today.year, today.month)[1]
    d = date(today.year, today.month, last_num)
    while not is_workday(d):
        d -= timedelta(days=1)
    return today == d

def actuals_updated_today() -> bool:
    if not ACTUALS_FILE.exists(): return False
    with open(ACTUALS_FILE) as f:
        data = json.load(f)
    return data.get("last_updated", "").startswith(date.today().isoformat())

# ── 数据加载 ──
def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 债券数据获取与存储 ──
def fetch_gov_bonds():
    """获取10Y国债全量历史（东方财富）"""
    import akshare as ak
    df = ak.bond_zh_us_rate()
    df = df.rename(columns={"日期": "date", "中国国债收益率10年": "gov_10y"})
    df["date"] = df["date"].astype(str)
    df["gov_10y"] = pd.to_numeric(df["gov_10y"], errors="coerce")
    return df[["date", "gov_10y"]].dropna()

def fetch_cdb_ieb_month(symbol: str, year: int, month: int):
    """获取指定月份的国开债/进出口债数据（中国货币网）"""
    import akshare as ak
    start = f"{year}{month:02d}01"
    end = f"{year}{month:02d}{calendar.monthrange(year,month)[1]}"
    try:
        df = ak.bond_china_close_return(symbol=symbol, period="1", start_date=start, end_date=end)
        df = df.rename(columns={"日期": "date", "到期收益率": "yield"})
        df["date"] = df["date"].astype(str)
        df["yield"] = pd.to_numeric(df["yield"], errors="coerce")
        # 筛选10年期
        df["期限"] = pd.to_numeric(df.get("期限", df.get("Term", 0)), errors="coerce")
        df = df[df["期限"] == 10] if "期限" in df.columns else df
        return df[["date", "yield"]].dropna()
    except Exception as e:
        print(f"    {symbol} {year}-{month:02d} 获取失败: {e}")
        return None

def update_bond_yields() -> Tuple[dict, int]:
    """更新 bond_yields.json，追加新日期数据，返回 (data, 新增行数)"""
    import pandas as pd
    data = load_json(BOND_FILE)
    existing = data.get("data", [])
    existing_dates = {r["date"] for r in existing}
    now = datetime.now()
    
    new_rows = 0
    is_first = len(existing) == 0
    print(f"[债券数据] 现有 {len(existing)} 条，{'首次运行需批量拉取' if is_first else '增量更新'}")

    # ── 国债 ──
    print("  拉取10Y国债全量...")
    df_gov = fetch_gov_bonds()
    gov_col = "gov_10y"
    
    # ── 国开债 ──
    if is_first:
        print("  首次批量拉取国开债（2023.01 起）...")
        dfs_cdb = []
        for yr in range(2023, now.year + 1):
            for mo in range(1, 13):
                if yr == now.year and mo > now.month:
                    break
                df_m = fetch_cdb_ieb_month("政策性金融债(国开行)", yr, mo)
                if df_m is not None and len(df_m) > 0:
                    dfs_cdb.append(df_m)
                time.sleep(0.5)
        df_cdb = pd.concat(dfs_cdb, ignore_index=True) if dfs_cdb else pd.DataFrame()
    else:
        latest_d = max(existing_dates) if existing_dates else "2023-01-01"
        ly, lm = int(latest_d[:4]), int(latest_d[5:7])
        print(f"  增量拉取国开债（{ly}-{lm:02d} 起）...")
        dfs_cdb = []
        for yr in range(ly, now.year + 1):
            start_mo = lm if yr == ly else 1
            for mo in range(start_mo, 13):
                if yr == now.year and mo > now.month:
                    break
                df_m = fetch_cdb_ieb_month("政策性金融债(国开行)", yr, mo)
                if df_m is not None and len(df_m) > 0:
                    dfs_cdb.append(df_m)
                time.sleep(0.5)
        df_cdb = pd.concat(dfs_cdb, ignore_index=True) if dfs_cdb else pd.DataFrame()
    
    if not df_cdb.empty:
        cdb_dict = dict(zip(df_cdb["date"].astype(str), df_cdb["yield"]))
    else:
        cdb_dict = {}

    # ── 进出口债 ──
    if is_first:
        print("  首次批量拉取进出口债（2023.01 起）...")
        dfs_ieb = []
        for yr in range(2023, now.year + 1):
            for mo in range(1, 13):
                if yr == now.year and mo > now.month:
                    break
                df_m = fetch_cdb_ieb_month("政策性金融债(进出口行)", yr, mo)
                if df_m is not None and len(df_m) > 0:
                    dfs_ieb.append(df_m)
                time.sleep(0.5)
        df_ieb = pd.concat(dfs_ieb, ignore_index=True) if dfs_ieb else pd.DataFrame()
    else:
        dfs_ieb = []
        for yr in range(ly, now.year + 1):
            start_mo = lm if yr == ly else 1
            for mo in range(start_mo, 13):
                if yr == now.year and mo > now.month:
                    break
                df_m = fetch_cdb_ieb_month("政策性金融债(进出口行)", yr, mo)
                if df_m is not None and len(df_m) > 0:
                    dfs_ieb.append(df_m)
                time.sleep(0.5)
        df_ieb = pd.concat(dfs_ieb, ignore_index=True) if dfs_ieb else pd.DataFrame()
    
    if not df_ieb.empty:
        ieb_dict = dict(zip(df_ieb["date"].astype(str), df_ieb["yield"]))
    else:
        ieb_dict = {}

    # ── 合并：对每个交易日在 gov 中有数据的日期，查找 cdb/ieb 值 ──
    gov_dict = dict(zip(df_gov["date"].astype(str), df_gov["gov_10y"]))
    all_dates = sorted(set(gov_dict.keys()))
    
    new_entries = []
    for d in all_dates:
        if d not in existing_dates and d in gov_dict:
            entry = {
                "date": d,
                "gov_10y": round(float(gov_dict[d]), 4),
                "cdb_10y": round(float(cdb_dict[d]), 4) if d in cdb_dict else None,
                "ieb_10y": round(float(ieb_dict[d]), 4) if d in ieb_dict else None,
            }
            new_entries.append(entry)
    
    existing.extend(new_entries)
    data["data"] = existing
    data["last_updated"] = now.strftime("%Y-%m-%d")
    save_json(BOND_FILE, data)
    
    new_rows = len(new_entries)
    print(f"  追加 {new_rows} 条新数据，共 {len(existing)} 条")
    return data, new_rows

# ── MA 计算 ──
def compute_ma(bond_data: list, comp_date: str, window: int, field: str) -> float:
    """计算指定字段在截止日期前的移动平均"""
    cutoff = comp_date[:10] if len(comp_date) > 10 else comp_date
    values = [r[field] for r in bond_data if r["date"] <= cutoff and r.get(field) is not None]
    if not values:
        return np.nan
    n = min(window, len(values))
    return float(np.mean(values[-n:]))

def compute_spread_ma(bond_data: list, comp_date: str, window: int) -> float:
    """计算 max(cdb-gov, ieb-gov) 的移动平均"""
    cutoff = comp_date[:10] if len(comp_date) > 10 else comp_date
    eligible = [r for r in bond_data if r["date"] <= cutoff]
    spreads = []
    for r in eligible[-window:]:
        if r.get("cdb_10y") is not None and r.get("gov_10y") is not None:
            s1 = r["cdb_10y"] - r["gov_10y"]
        else:
            s1 = None
        if r.get("ieb_10y") is not None and r.get("gov_10y") is not None:
            s2 = r["ieb_10y"] - r["gov_10y"]
        else:
            s2 = None
        if s1 is not None or s2 is not None:
            spreads.append(max(s1 if s1 is not None else -99, s2 if s2 is not None else -99))
    if not spreads:
        return 0.0912  # 默认利差
    return float(np.mean(spreads))

# ── 公式 ──
def apply_segment(pre_val: float) -> float:
    for low, high, coeff in SEGMENT_COEFF:
        if low < pre_val <= high:
            return pre_val * coeff
    return pre_val

def compute_prediction(comp_date: str, bond_data: list, lpr_history: list = None, deposit_history: list = None) -> dict:
    """计算指定截止日期的预定利率研究值"""
    comp_dt = date.fromisoformat(comp_date[:10] if len(comp_date) > 10 else comp_date)
    
    # 参考利率：6个月 LPR+定存 均值的 MA
    ref_rates = []
    for i in range(5, -1, -1):
        y, m = comp_dt.year, comp_dt.month - i
        while m <= 0:
            y -= 1; m += 12
        ref_rates.append((get_lpr_for_month(y, m, lpr_history) + get_deposit_for_month(y, m, deposit_history)) / 2)
    ref_rate = float(np.mean(ref_rates))
    
    # MA250/750
    ma250_gov = compute_ma(bond_data, comp_date, 250, "gov_10y")
    ma750_gov = compute_ma(bond_data, comp_date, 750, "gov_10y")
    spread_250 = compute_spread_ma(bond_data, comp_date, 250)
    spread_750 = compute_spread_ma(bond_data, comp_date, 750)
    
    base_250 = ma250_gov + spread_250
    base_750 = ma750_gov + spread_750
    base_return = min(base_250, base_750)
    pre_adj = min(ref_rate, base_return)
    predicted = apply_segment(pre_adj)
    
    return {
        "ref_rate": round(ref_rate, 4),
        "base_return": round(base_return, 4),
        "ma250_gov": round(ma250_gov, 4),
        "ma750_gov": round(ma750_gov, 4),
        "spread_250": round(spread_250, 4),
        "spread_750": round(spread_750, 4),
        "predicted": round(predicted, 4),
    }

# ── 预测季度 ──
def get_prediction_quarters() -> List[Dict]:
    """基于 actuals.json 最新值，确定需预测的4个季度"""
    actuals_data = load_json(ACTUALS_FILE)
    actuals = actuals_data.get("actuals", [])
    if not actuals:
        return []
    latest = actuals[-1]
    latest_q = latest["quarter"]
    year = int(latest_q[:4])
    q = int(latest_q[5:])
    
    quarters = []
    for _ in range(4):
        q += 1
        if q > 4:
            q = 1; year += 1
        quarter = f"{year}Q{q}"
        announce_map = {1: f"{year}年4月", 2: f"{year}年7月", 3: f"{year}年10月", 4: f"{year+1}年1月"}
        comp_month_map = {1: 3, 2: 6, 3: 9, 4: 12}
        comp_date = f"{year}-{comp_month_map[q]:02d}-{calendar.monthrange(year, comp_month_map[q])[1]}"
        quarters.append({
            "quarter": quarter,
            "announced": announce_map[q],
            "comp_date": comp_date,
        })
    return quarters

# ── 校验 ──
def validate_predictions(new_preds: List[Dict], old_preds: List[Dict]) -> List[str]:
    warnings = []
    for i, new_p in enumerate(new_preds):
        if i < len(old_preds) and old_preds[i]["quarter"] == new_p["quarter"]:
            old_val = old_preds[i]["predicted_value"]
            change_bp = abs(new_p["predicted_value"] - old_val) * 100
            if change_bp > VALIDATION_MAX_CHANGE_BP:
                warnings.append(f"⚠️ {new_p['quarter']} 预测值变动 {change_bp:.1f}BP（上期 {old_val}%），超过 {VALIDATION_MAX_CHANGE_BP}BP")
        # 单季度合理性
        if new_p["predicted_value"] < 0.5 or new_p["predicted_value"] > 4.0:
            warnings.append(f"⚠️ {new_p['quarter']} 预测值 {new_p['predicted_value']}% 明显异常")
    return warnings

# ── 日志 ──
def write_log(status: str, detail: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"auto-update-{date.today().isoformat()}.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 预测值自动更新日志 - {now_str}", "", f"## 执行状态：{status}", "", detail]
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n---\n")
    print(f"\n[日志] {log_file}")

# ── 主逻辑 ──
def main():
    print("=" * 60)
    print(f"预定利率研究值 — 预测值自动更新  {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 60)
    
    force = os.environ.get("FORCE_UPDATE", "").lower() == "true"
    
    # ── 触发判断 ──
    if not force:
        triggered = False
        reason = ""
        if is_first_working_day():
            triggered = True; reason = "本月首个工作日"
        elif is_last_working_day():
            triggered = True; reason = "本月末个工作日"
        elif actuals_updated_today():
            triggered = True; reason = "实际值今日已更新"
        if not triggered:
            print(f"\n[SKIP] 无需更新（非首个/末个工作日，且实际值今日未更新）")
            sys.exit(0)
        print(f"\n[触发] {reason}")
    
    # ── 加载/更新LPR和定存利率 ──
    print("\n[LPR] 获取5年期LPR历史...")
    lpr_history = load_lpr_history()
    print(f"  共 {len(lpr_history)} 条调整记录，最新 {lpr_history[-1][1]}%（{lpr_history[-1][0]}）")
    
    print("[定存] 检查六大行定存利率调整...")
    dep_updated = check_deposit_rate_news()
    deposit_history = load_deposit_history()
    print(f"  {'发现新调整！' if dep_updated else '无新调整'}，最新 {deposit_history[-1][1]}%（{deposit_history[-1][0]}）")
    
    # ── 更新债券数据 ──
    bond_data, new_rows = update_bond_yields()
    bond_list = bond_data.get("data", [])
    print(f"[债券] 共 {len(bond_list)} 条日频数据")
    
    if len(bond_list) < 100:
        print("[WARN] 债券数据不足100条，预测可能不准确")
    
    # ── 预测 ──
    quarters = get_prediction_quarters()
    if not quarters:
        print("[ERR] 无法确定预测季度（actuals.json 为空）")
        write_log("未更新", "### 原因\nactuals.json 为空，无法确定预测季度。")
        sys.exit(0)
    
    print(f"\n[预测] 基于 {len(bond_list)} 条债券数据，预测 {len(quarters)} 个季度")
    
    new_predictions = []
    for q in quarters:
        result = compute_prediction(q["comp_date"], bond_list, lpr_history, deposit_history)
        gap_bp = round((MAX_RATE - result["predicted"]) * 100, 1)
        entry = {
            "quarter": q["quarter"],
            "announced": q["announced"],
            "predicted_value": result["predicted"],
            "ref_rate": result["ref_rate"],
            "base_return": result["base_return"],
            "ma250_gov": result["ma250_gov"],
            "ma750_gov": result["ma750_gov"],
            "spread_250": result["spread_250"],
            "spread_750": result["spread_750"],
            "max_rate": MAX_RATE,
            "gap_bp": gap_bp,
            "trigger": gap_bp >= TRIGGER_THRESHOLD * 100,
        }
        new_predictions.append(entry)
        print(f"  {q['quarter']} ({q['announced']}): {result['predicted']:.4f}% (差值 {gap_bp}BP)")
    
    # ── 校验 ──
    old_data = load_json(PREDICTIONS_FILE)
    old_preds = old_data.get("predictions", [])
    warnings = validate_predictions(new_predictions, old_preds)
    if warnings:
        print(f"\n[校验] {len(warnings)} 条告警:")
        for w in warnings:
            print(f"  {w}")
    
    # ── 保存 ──
    lpr = get_lpr_for_month(datetime.now().year, datetime.now().month)
    deposit = get_deposit_for_month(datetime.now().year, datetime.now().month)
    latest_gov = bond_list[-1]["gov_10y"] if bond_list else None
    
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "method": "平推法",
        "description": "预定利率研究值模型预测",
        "base_data": {
            "lpr_5y": lpr,
            "deposit_5y": deposit,
            "bond_yield_10y": latest_gov,
        },
        "predictions": new_predictions,
        "validation_warnings": warnings,
    }
    save_json(PREDICTIONS_FILE, output)
    print(f"\n[DONE] 预测值已保存到 {PREDICTIONS_FILE.name}")
    
    # ── 日志 ──
    detail = f"""### 触发原因
{reason if not force else '强制更新（手动触发）'}

### 债券数据
- 数据条数：{len(bond_list)}（新增 {new_rows} 条）
- 最新10Y国债：{latest_gov}%
- 5Y LPR：{lpr}%
- 5Y定存：{deposit}%

### 预测结果
| 季度 | 公布时间 | 预测值(%) | MA250_gov | MA750_gov | 利差250 | 利差750 | 差值(BP) |
|------|----------|-----------|-----------|-----------|---------|---------|----------|
"""
    for p in new_predictions:
        detail += f"| {p['quarter']} | {p['announced']} | {p['predicted_value']:.4f} | {p['ma250_gov']:.4f} | {p['ma750_gov']:.4f} | {p['spread_250']:.4f} | {p['spread_750']:.4f} | {p['gap_bp']:.1f} |\n"
    
    if warnings:
        detail += "\n### 校验告警\n" + "\n".join(f"- {w}" for w in warnings)
    else:
        detail += "\n### 校验\n无异常"
    
    write_log("已更新" if not warnings else "已更新（有告警）", detail)
    
    # ── 触发汇总 ──
    triggered_quarters = [p["quarter"] for p in new_predictions if p["trigger"]]
    if triggered_quarters:
        print(f"\n⚠️ 触发预警：{', '.join(triggered_quarters)} 差值≥25BP！")

if __name__ == "__main__":
    import pandas as pd
    main()
