#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步 index.html 的离线快照（SNAPSHOT_UPDATED + FALLBACK_PREDICTIONS）到 data/predictions.json。

背景：
  index.html 内嵌一份 predictions 离线副本，仅用于本地 file:// 直接打开时显示预测值。
  为防分叉，run_checklist.py 的 F8 要求 SNAPSHOT_UPDATED == predictions.json.last_updated。
  predictions.json 更新后，运行本脚本把最新值写回 index.html，使两者重新一致。

用法：python scripts/sync_index_snapshot.py
幂等：无变化则不改动文件（仅更新 SNAPSHOT_UPDATED 与 FALLBACK_PREDICTIONS 两段）。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED_FILE = os.path.join(ROOT, "data", "predictions.json")
INDEX_FILE = os.path.join(ROOT, "index.html")


def main():
    with open(PRED_FILE, encoding="utf-8") as f:
        pred = json.load(f)
    last_updated = pred["last_updated"]
    snap = pred.get("predictions", [])

    with open(INDEX_FILE, encoding="utf-8") as f:
        html = f.read()

    # 1) 更新 SNAPSHOT_UPDATED
    html, n1 = re.subn(
        r'(SNAPSHOT_UPDATED\s*=\s*")[^"]*(")',
        lambda m: m.group(1) + last_updated + m.group(2),
        html, count=1,
    )

    # 2) 重建 FALLBACK_PREDICTIONS 数组
    items = []
    for p in snap:
        kv = ", ".join(
            f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in p.items()
        )
        items.append("    { " + kv + " }")
    arr = "[\n" + ",\n".join(items) + "\n];"
    html, n2 = re.subn(
        r"const FALLBACK_PREDICTIONS = \[.*?\];",
        "const FALLBACK_PREDICTIONS = " + arr,
        html, count=1, flags=re.S,
    )

    if n1 == 0 or n2 == 0:
        raise SystemExit(
            "未能在 index.html 中找到 SNAPSHOT_UPDATED 或 FALLBACK_PREDICTIONS，"
            "请检查页面结构。n1=%d, n2=%d" % (n1, n2)
        )

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html 离线快照已同步：SNAPSHOT_UPDATED={last_updated}，"
          f"predictions={len(snap)} 条（SNAPSHOT_UPDATED 替换 {n1} 处，数组替换 {n2} 处）。")


if __name__ == "__main__":
    main()
