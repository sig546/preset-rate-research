#!/usr/bin/env python3
"""
平安人寿 — 产品预定利率公告检核脚本
===================================================
功能：访问平安人寿信息披露页面，检查是否有新的预定利率公告。
      若检测到新公告，提取普通型保险产品的最高值及生效时间。
      更新 data/pingan_announcements.json。

运行环境：GitHub Actions (ubuntu-latest)
依赖：pip install requests beautifulsoup4
"""

import json
import re
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# -------------------------------------------------------
# 配置
# -------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PINGAN_FILE = PROJECT_ROOT / "data" / "pingan_announcements.json"

# 平安人寿信息披露页面
PINGAN_PAGE_URL = "https://life.pingan.com/p/#/list-page?disclosureChannel=ilifeInfoDisclosure&disclosureName=%E4%BA%A7%E5%93%81%E9%A2%84%E5%AE%9A%E5%88%A9%E7%8E%87%E5%85%AC%E5%91%8A&disclosureId=e594db5b25bf4b5e9e758cacf64a289f"

# 提取公告标题中日期的正则
DATE_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
DATE_ISO_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

# 提取公告内容中最高值的正则
MAX_RATE_PATTERN = re.compile(r"普通型保险产品预定利率最高值[为：]\s*(\d+\.?\d*)\s*%")
# 提取生效时间的正则
EFFECTIVE_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日.*?时起不[再在]接受")
EFFECTIVE_PATTERN2 = re.compile(r"自\s*(\d{4})年(\d{1,2})月(\d{1,2})日.*?生效")

# -------------------------------------------------------
# 搜索函数
# -------------------------------------------------------
def search_news(keyword: str) -> List[Dict]:
    """搜索新闻获取平安人寿公告信息"""
    results = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(keyword, max_results=10):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": r.get("href", ""),
                })
    except Exception as e:
        print(f"  [WARN] DuckDuckGo 搜索失败: {e}")

    # 同时尝试新华网搜索
    try:
        import urllib.request
        import urllib.parse
        encoded = urllib.parse.quote(keyword)
        url = f"https://so.news.cn/getNews?keyword={encoded}&curPage=1&sortField=0&searchFields=1&lang=cn"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            for item in data.get("content", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "body": item.get("description", ""),
                    "href": item.get("url", ""),
                })
    except Exception as e:
        print(f"  [INFO] 新华网搜索不可用: {e}")

    return results

def try_fetch_page() -> Optional[str]:
    """尝试直接获取平安人寿页面HTML"""
    import requests
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(PINGAN_PAGE_URL, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"  [INFO] 直接获取页面失败: {e}")
    return None

# -------------------------------------------------------
# 解析函数
# -------------------------------------------------------
def extract_announcements_from_text(text: str) -> List[Dict]:
    """
    从搜索结果或页面文本中提取公告信息。
    返回 [{title, date, max_rate, effective_date}, ...]
    """
    found = []

    # 在摘要中搜索最高值和生效时间
    max_rate_match = MAX_RATE_PATTERN.search(text)
    if not max_rate_match:
        return found

    max_rate = float(max_rate_match.group(1))

    # 提取日期
    date_match = DATE_PATTERN.search(text)
    date_str = None
    if date_match:
        y, m, d = date_match.groups()
        date_str = f"{y}-{int(m):02d}-{int(d):02d}"

    # 如果标题日期未找到，尝试 ISO 格式
    if not date_str:
        iso_match = DATE_ISO_PATTERN.search(text)
        if iso_match:
            date_str = iso_match.group(1)

    # 提取生效时间
    effective_date = None
    eff_match = EFFECTIVE_PATTERN.search(text) or EFFECTIVE_PATTERN2.search(text)
    if eff_match:
        y, m, d = eff_match.groups()
        effective_date = f"{y}-{int(m):02d}-{int(d):02d}"

    if max_rate:
        found.append({
            "max_rate": max_rate,
            "date": date_str,
            "effective_date": effective_date,
        })

    return found

def extract_announcement_date(title: str) -> Optional[str]:
    """从公告标题中提取日期"""
    match = DATE_PATTERN.search(title)
    if match:
        y, m, d = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    match = DATE_ISO_PATTERN.search(title)
    if match:
        return match.group(1)
    return None

def parse_announcement_content(content_text: str) -> Dict:
    """
    解析公告详细内容，提取最高值和生效时间。
    """
    result = {"max_rate": None, "effective_date": None}

    # 提取最高值
    max_match = MAX_RATE_PATTERN.search(content_text)
    if max_match:
        result["max_rate"] = float(max_match.group(1))

    # 提取生效时间
    eff_match = EFFECTIVE_PATTERN.search(content_text)
    if eff_match:
        y, m, d = eff_match.groups()
        result["effective_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
    else:
        eff_match = EFFECTIVE_PATTERN2.search(content_text)
        if eff_match:
            y, m, d = eff_match.groups()
            result["effective_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

    return result

# -------------------------------------------------------
# 主逻辑
# -------------------------------------------------------
def main():
    print("=" * 60)
    print("平安人寿 — 产品预定利率公告检核")
    print(f"运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 加载已有公告数据
    known = {"announcements": []}
    if PINGAN_FILE.exists():
        with open(PINGAN_FILE, "r", encoding="utf-8") as f:
            known = json.load(f)

    known_dates = {a["date"] for a in known.get("announcements", []) if a.get("date")}
    print(f"[状态] 已记录 {len(known_dates)} 条公告: {sorted(known_dates)}")

    # 2. 搜索最新公告
    print("\n[搜索] 关键词: 平安人寿 预定利率 公告")
    results = search_news("平安人寿 预定利率 公告")

    # 3. 从搜索结果中提取公告日期
    potential_new = []
    for r in results:
        text = r["title"] + " " + r["body"]
        # 检查是否提到了预定利率公告
        if "平安人寿" in text and ("预定利率" in text) and ("公告" in text):
            date = extract_announcement_date(r["title"])
            if date and date not in known_dates:
                # 提取公告中的关键数据
                parsed = parse_announcement_content(text)
                if parsed["max_rate"]:
                    potential_new.append({
                        "title": r["title"],
                        "date": date,
                        "max_rate": parsed["max_rate"],
                        "effective_date": parsed.get("effective_date"),
                        "source_url": r["href"],
                    })

    # 4. 去重
    seen_dates = set()
    unique_new = []
    for a in potential_new:
        if a["date"] not in seen_dates:
            seen_dates.add(a["date"])
            unique_new.append(a)

    if unique_new:
        print(f"\n[发现] {len(unique_new)} 条新公告:")
        for a in unique_new:
            print(f"  • {a['date']}: 普通型最高值 {a['max_rate']}%"
                  + (f", {a['effective_date']} 生效" if a.get('effective_date') else ""))
            print(f"    来源: {a['source_url'][:80]}")
    else:
        print("\n[结果] 未发现新公告")

    # 5. 更新数据文件
    new_added = False
    for a in unique_new:
        entry = {
            "id": a["date"],
            "title": "平安人寿关于人身保险产品预定利率的公告",
            "date": a["date"],
            "product_type": "普通型",
            "max_rate": a["max_rate"],
            "effective_date": a.get("effective_date") or a["date"],
            "source_url": a.get("source_url", ""),
        }
        known["announcements"].append(entry)
        new_added = True

    if new_added:
        known["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(PINGAN_FILE, "w", encoding="utf-8") as f:
            json.dump(known, f, ensure_ascii=False, indent=2)
        print(f"\n[DONE] 已追加 {len(unique_new)} 条新公告到 {PINGAN_FILE.name}")

    # 6. 输出最新公告摘要（供其他脚本使用）
    if known["announcements"]:
        latest = known["announcements"][-1]
        print(f"\n[最新公告]")
        print(f"  日期: {latest['date']}")
        print(f"  普通型最高值: {latest['max_rate']}%")
        print(f"  生效时间: {latest.get('effective_date', 'N/A')}")

if __name__ == "__main__":
    main()
