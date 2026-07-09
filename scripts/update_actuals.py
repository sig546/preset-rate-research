#!/usr/bin/env python3
"""
预定利率研究值 — 实际值自动更新脚本（v2）
====================================================
变更（v2）：
  - 移除数值范围 1.50~2.50 和 ±50BP 变动幅度校验
  - 保留交叉验证（≥2 来源一致）
  - 每次运行生成 Markdown 工作日志
  - 更新完成后自动调用平安人寿公告检核
"""

import json
import re
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
from collections import Counter

# -------------------------------------------------------
# 配置
# -------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTUALS_FILE = PROJECT_ROOT / "data" / "actuals.json"
LOGS_DIR = PROJECT_ROOT / "logs"

# 研究值提取正则
VALUE_PATTERN = re.compile(r"研究值[为：]\s*(\d+\.\d+)\s*%")

# -------------------------------------------------------
# 工具函数
# -------------------------------------------------------
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M")

# -------------------------------------------------------
# 日期 / 季度
# -------------------------------------------------------
def get_expected_quarter_and_announced() -> Optional[Tuple[str, str]]:
    now = datetime.now()
    year, month = now.year, now.month
    mapping = {
        1:  (f"{year-1}Q4", f"{year}年1月"),
        4:  (f"{year}Q1",   f"{year}年4月"),
        7:  (f"{year}Q2",   f"{year}年7月"),
        10: (f"{year}Q3",   f"{year}年10月"),
    }
    return mapping.get(month)

def in_update_window() -> bool:
    return 20 <= datetime.now().day <= 31

# -------------------------------------------------------
# 数据加载
# -------------------------------------------------------
def load_actuals() -> dict:
    if ACTUALS_FILE.exists():
        with open(ACTUALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": "", "description": "", "actuals": []}

def save_actuals(data: dict) -> None:
    data["last_updated"] = now_str()
    with open(ACTUALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def quarter_exists(data: dict, quarter: str) -> bool:
    return any(a["quarter"] == quarter for a in data.get("actuals", []))

# -------------------------------------------------------
# 搜索
# -------------------------------------------------------
def search_ddg(keyword: str, max_results: int = 15) -> List[dict]:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(keyword, max_results=max_results):
                results.append({"title": r.get("title",""), "body": r.get("body",""), "href": r.get("href","")})
        return results
    except Exception as e:
        print(f"  DuckDuckGo 失败: {e}")
        return []

def search_xinhua(keyword: str) -> List[dict]:
    results = []
    try:
        import urllib.request, urllib.parse
        encoded = urllib.parse.quote(keyword)
        url = f"https://so.news.cn/getNews?keyword={encoded}&curPage=1&sortField=0&searchFields=1&lang=cn"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            for item in data.get("content", {}).get("results", []):
                results.append({"title": item.get("title",""), "body": item.get("description",""), "href": item.get("url","")})
    except Exception as e:
        print(f"  新华网不可用: {e}")
    return results

def extract_values(results: List[dict]) -> List[Tuple[float, str, str]]:
    found = []
    for r in results:
        text = r["title"] + " " + r["body"]
        m = VALUE_PATTERN.search(text)
        if m:
            found.append((float(m.group(1)), r["title"], r["href"]))
    return found

def cross_validate(candidate: float, sources: List[Tuple[float, str, str]]) -> bool:
    value_counts = Counter(v for v, _, _ in sources)
    max_count = value_counts.get(candidate, 0)
    if max_count >= 2:
        print(f"  交叉验证通过: {candidate}% 在 {max_count} 个来源中一致")
        return True
    print(f"  交叉验证失败: {candidate}% 仅出现在 {max_count} 个来源（需 ≥2）")
    return False

# -------------------------------------------------------
# 最高值判断
# -------------------------------------------------------
def get_max_rate(announced: str) -> float:
    # 2025年9月1日起最高值降至2.00%
    # 对应于 2025年10月 及之后公布的值
    try:
        parts = announced.replace("年"," ").replace("月","").split()
        year, month = int(parts[0]), int(parts[1])
        if year < 2025 or (year == 2025 and month <= 7):
            return 2.50
    except:
        pass
    return 2.00

# -------------------------------------------------------
# 日志
# -------------------------------------------------------
def write_log(status: str, details: str, pingan_result: Optional[str] = None) -> None:
    """生成 Markdown 工作日志"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"auto-update-{now_date()}.md"

    lines = []
    lines.append(f"# 自动更新日志 - {now_str()}")
    lines.append("")
    lines.append(f"## 执行状态：{status}")
    lines.append("")
    lines.append(details)

    if pingan_result:
        lines.append("")
        lines.append(pingan_result)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n---\n")

    print(f"\n[日志] 已写入 {log_file}")

# -------------------------------------------------------
# 主逻辑
# -------------------------------------------------------
def main():
    print("=" * 60)
    print("预定利率研究值 — 实际值自动更新 v2")
    print(f"运行时间：{now_str()}")
    print("=" * 60)

    force = os.environ.get("FORCE_UPDATE", "false").lower() == "true"
    skip_reason = None

    # 0. 窗口检查
    if not force and not in_update_window():
        skip_reason = f"当前不在更新窗口期（{datetime.now().day}日，窗口期为20日至月末）"
        print(f"\n[SKIP] {skip_reason}")
        write_log("未更新", f"### 原因\n{skip_reason}")
        sys.exit(0)

    # 1. 确定目标季度
    expected = get_expected_quarter_and_announced()
    if expected is None:
        skip_reason = f"当前月份 {datetime.now().month} 不在更新月份列表（1/4/7/10月）"
        print(f"\n[SKIP] {skip_reason}")
        write_log("未更新", f"### 原因\n{skip_reason}")
        sys.exit(0)

    target_quarter, target_announced = expected
    print(f"\n[目标] {target_quarter}（{target_announced}公布）")

    # 2. 检查是否已存在
    data = load_actuals()
    if not force and quarter_exists(data, target_quarter):
        skip_reason = f"{target_quarter} 的研究值已存在（{data['actuals'][-1]['value']}%），本次窗口不再重复更新"
        print(f"\n[SKIP] {skip_reason}")
        write_log("未更新", f"### 原因\n{skip_reason}")
        sys.exit(0)

    # 3. 搜索并提取
    print("\n[搜索] 预定利率研究值")
    all_results = search_ddg("预定利率研究值", 15)
    all_results.extend(search_xinhua("预定利率研究值"))
    print(f"  共 {len(all_results)} 条结果")

    if not all_results:
        write_log("未更新", f"### 原因\n搜索无结果（目标：{target_quarter}）")
        sys.exit(0)

    found = extract_values(all_results)
    print(f"\n[提取] 匹配到 {len(found)} 个数值:")
    for v, t, _ in found:
        print(f"  • {v}% — {t[:60]}")

    if not found:
        write_log("未更新", f"### 原因\n未匹配到研究值（目标：{target_quarter}）")
        sys.exit(0)

    # 4. 确定候选值
    value_counter = Counter(v for v, _, _ in found)
    candidate_val, candidate_count = value_counter.most_common(1)[0]
    print(f"\n[候选] {candidate_val}%（出现 {candidate_count} 次）")

    # 5. 交叉验证（唯一保留的安全校验）
    if not cross_validate(candidate_val, found):
        write_log("未更新", f"### 原因\n交叉验证未通过\n- 候选值：{candidate_val}%\n- 来源分布：{dict(value_counter)}")
        sys.exit(1)

    # 6. 计算元数据
    previous_val = data["actuals"][-1]["value"] if data["actuals"] else None
    change_bp = round((candidate_val - previous_val) * 100, 1) if previous_val is not None else None
    max_rate = get_max_rate(target_announced)

    # 7. 追加
    new_entry = {
        "quarter": target_quarter,
        "announced": target_announced,
        "value": candidate_val,
        "max_rate": max_rate,
        "change_bp": change_bp,
        "note": f"自动更新（{now_date()}）"
    }
    data["actuals"].append(new_entry)
    save_actuals(data)
    print(f"\n[DONE] 已追加: {target_quarter} = {candidate_val}%（{target_announced}公布）")

    # 8. 生成更新日志
    detail = f"""### 实际值更新
- **目标季度**：{target_quarter}
- **公布时间**：{target_announced}
- **更新后数值**：{candidate_val}%
- **环比变动**：{change_bp:+d} BP
- **最高值**：{max_rate}%
- **搜索来源**：DuckDuckGo + 新华网（共 {len(all_results)} 条结果）
- **交叉验证**：通过（{candidate_count} 个来源一致）
- **来源明细**：
"""
    for v, t, h in found:
        detail += f"  - {v}% — [{t[:50]}]({h})\n"
    detail += f"\n### 数据文件\n- 当前共 {len(data['actuals'])} 条记录"

    # 9. 调用平安人寿检核
    pingan_result = None
    try:
        print("\n[平安] 调用平安人寿公告检核...")
        result = subprocess.run(
            ["python", str(PROJECT_ROOT / "scripts" / "check_pingan.py")],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120
        )
        pingan_output = result.stdout.strip()
        if "未发现新公告" in pingan_output:
            pingan_result = "### 平安人寿公告检核\n- 检核时间：{} GMT\n- 结果：未发现新公告".format(now_str())
        elif "新公告" in pingan_output:
            pingan_result = "### 平安人寿公告检核\n" + pingan_output[-500:]
        else:
            pingan_result = f"### 平安人寿公告检核\n- 结果：{pingan_output[:300]}"
        print(pingan_output[:200])
    except Exception as e:
        pingan_result = f"### 平安人寿公告检核\n- 错误：{e}"
        print(f"  [ERR] 平安检核失败: {e}")

    write_log("已更新", detail, pingan_result)

if __name__ == "__main__":
    main()
