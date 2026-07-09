import akshare as ak
import pandas as pd

# 尝试获取10年期国债收益率数据
print("=== 尝试获取中债国债收益率数据 ===")

# 方法1: 获取中债国债收益率曲线数据
try:
    # 获取中债国债收益率曲线
    bond_china_yield_df = ak.bond_china_yield(start_date="20250101", end_date="20251231")
    print(bond_china_yield_df.head(20))
    print("\n数据列:", bond_china_yield_df.columns.tolist())
except Exception as e:
    print(f"方法1失败: {e}")

# 方法2: 获取国债收益率数据
try:
    bond_zh_us_rate_df = ak.bond_zh_us_rate(start_date="20250101", end_date="20251231")
    print("\n=== 国债收益率数据 ===")
    print(bond_zh_us_rate_df.head(20))
    print("\n数据列:", bond_zh_us_rate_df.columns.tolist())
except Exception as e:
    print(f"方法2失败: {e}")

# 方法3: 中国债券信息网
try:
    bond_china_close_df = ak.bond_china_close(start_date="20250101", end_date="20251231")
    print("\n=== 债券收盘数据 ===")
    print(bond_china_close_df.head(20))
except Exception as e:
    print(f"方法3失败: {e}")
