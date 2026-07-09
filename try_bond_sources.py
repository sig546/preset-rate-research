import akshare as ak
import pandas as pd

# 尝试获取银行间债券现券报价数据
print("=== 尝试获取 bond_spot_quote ===")
try:
    df = ak.bond_spot_quote()
    print(f"获取到 {len(df)} 条数据")
    print("列名:", df.columns.tolist())
    print("\n前10行:")
    print(df.head(10))
except Exception as e:
    print(f"失败: {e}")

# 尝试获取中债估值-债券信息
print("\n=== 尝试获取 bond_info_cm ===")
try:
    df2 = ak.bond_info_cm()
    print(f"获取到 {len(df2)} 条数据")
    print("列名:", df2.columns.tolist()[:20])
    # 搜索国开债和进出口债
    gk = df2[df2['债券简称'].str.contains('国开', na=False)]
    jk = df2[df2['债券简称'].str.contains('进出', na=False)]
    print(f"\n国开债: {len(gk)} 条")
    print(f"进出口债: {len(jk)} 条")
    if len(gk) > 0:
        print(gk[['债券简称', '债券代码', '到期收益率']].head())
    if len(jk) > 0:
        print(jk[['债券简称', '债券代码', '到期收益率']].head())
except Exception as e:
    print(f"失败: {e}")
