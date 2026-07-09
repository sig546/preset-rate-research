import akshare as ak
import pandas as pd
import numpy as np

# 获取2025年中债国债收益率曲线数据
print("=== 获取2025年国债收益率数据 ===")
df = ak.bond_china_yield(start_date="20250101", end_date="20251231")

# 筛选中债国债收益率曲线
gz_df = df[df['曲线名称'] == '中债国债收益率曲线'].copy()
gz_df['日期'] = pd.to_datetime(gz_df['日期'])
gz_df = gz_df.sort_values('日期')

print(f"获取到 {len(gz_df)} 条国债数据")
print("\n各月末10年期国债收益率:")

# 提取各月末数据
gz_df['年月'] = gz_df['日期'].dt.to_period('M')
monthly_gz = gz_df.groupby('年月')['10年'].last()
for month, val in monthly_gz.items():
    print(f"  {month}: {val:.4f}%")

# 获取2025年国开债数据
print("\n=== 获取2025年国开债收益率数据 ===")
try:
    # 搜索国开债相关数据
    df2 = ak.bond_china_yield(start_date="20250101", end_date="20251231")
    # 查看所有曲线名称
    print("可用曲线名称:")
    for name in df2['曲线名称'].unique():
        print(f"  - {name}")
except Exception as e:
    print(f"失败: {e}")

# 尝试获取国开债数据
print("\n=== 尝试获取国开债 ===")
try:
    # 搜索国开债
    gk_df = df2[df2['曲线名称'].str.contains('国开', na=False)]
    if len(gk_df) > 0:
        print("找到国开债数据:")
        print(gk_df['曲线名称'].unique())
    else:
        print("未找到国开债数据")
except Exception as e:
    print(f"失败: {e}")

# 尝试获取政策性金融债（进出口、农发）
print("\n=== 尝试获取政策性金融债 ===")
try:
    zc_df = df2[df2['曲线名称'].str.contains('政策性金融债|进出口|农发', na=False)]
    if len(zc_df) > 0:
        print("找到政策性金融债数据:")
        print(zc_df['曲线名称'].unique())
    else:
        print("未找到政策性金融债数据")
except Exception as e:
    print(f"失败: {e}")
