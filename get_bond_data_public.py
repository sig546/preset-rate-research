"""
使用akshare获取10年期国债日频收益率数据
数据来源：中国货币网 (www.chinamoney.com.cn / www.shibor.net.cn)
"""
import akshare as ak
import pandas as pd
from datetime import datetime

# 获取10年期国债收益率历史数据
# bond_china_yield 获取中债国债收益率曲线
print("=" * 60)
print("获取10年期国债收益率日频数据...")
print("=" * 60)

# 方法1: 使用 bond_china_yield
try:
    df = ak.bond_china_yield(start_date="2023-01-01", end_date="2026-07-02")
    print(f"\nbond_china_yield columns: {df.columns.tolist()}")
    print(f"Shape: {df.shape}")
    print(df.head(20))
    print("...")
    print(df.tail(20))
except Exception as e:
    print(f"bond_china_yield error: {e}")

# 方法2: 尝试获取国债收益率
print("\n" + "=" * 60)
print("尝试其他接口...")
print("=" * 60)

# 列出所有包含 'bond' 和 'yield' 的函数
funcs = [f for f in dir(ak) if 'bond' in f.lower() and ('yield' in f.lower() or 'rate' in f.lower())]
print(f"\n债券收益率相关接口: {funcs}")

# 尝试 bond_zh_us_rate
try:
    df2 = ak.bond_zh_us_rate()
    print(f"\nbond_zh_us_rate columns: {df2.columns.tolist()}")
    print(df2.tail(30))
except Exception as e:
    print(f"bond_zh_us_rate error: {e}")

# 方法3: 获取中美国债收益率对比
try:
    df3 = ak.bond_china_yield(start_date="20231201", end_date="20241231")
    print(f"\n2024年数据 columns: {df3.columns.tolist()}")
    print(f"Shape: {df3.shape}")
    print(df3.head(30))
except Exception as e:
    print(f"2024 bond error: {e}")
