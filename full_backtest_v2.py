"""
预定利率研究值 - 完整回溯验证（修正版）
======================================
"""

import pandas as pd
import numpy as np
from datetime import datetime

# ============== 读取数据 ==============
file_path = 'C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx'

# 读取国债收益率原始数据
df_gov_raw = pd.read_excel(file_path, sheet_name='国债-到期', header=None)

print("=" * 70)
print("预定利率研究值 - 回溯验证分析")
print("=" * 70)
print()

# 解析国债原始数据
# 行8开始是日期和期限收益率数据
# 列0是日期，后面列是不同期限(0-50年)
# 列11对应10年期国债

# 提取原始国债收益率
gov_dates = []
gov_yields = []

for idx in range(8, len(df_gov_raw)):
    row = df_gov_raw.iloc[idx]
    date_val = row.iloc[0]
    yield_10y = row.iloc[11] if len(row) > 11 else None  # 10年期

    if pd.notna(date_val) and '202' in str(date_val):
        gov_dates.append(pd.to_datetime(date_val))
        gov_yields.append(yield_10y / 100)  # 转换为小数形式

# 创建DataFrame
df_bond = pd.DataFrame({
    '日期': gov_dates,
    '10Y收益率': gov_yields
})
df_bond = df_bond.dropna()
df_bond = df_bond.sort_values('日期').reset_index(drop=True)

print(f"国债数据范围: {df_bond['日期'].min().date()} 至 {df_bond['日期'].max().date()}")
print(f"数据点数量: {len(df_bond)}")
print()

# 计算移动平均
df_bond['MA250'] = df_bond['10Y收益率'].rolling(window=250, min_periods=250).mean()
df_bond['MA750'] = df_bond['10Y收益率'].rolling(window=750, min_periods=750).mean()

print(f"10年期国债收益率最新数据:")
print(df_bond.tail(3).to_string(index=False))
print()

# ============== 税收溢价 ==============
TAX_PREMIUM_250 = 0.001386  # 0.1386%
TAX_PREMIUM_750 = 0.002224  # 0.2224%
REFERENCE_RATE = 0.027  # 2.7%

# ============== 计算基础回报水平和预定利率 ==============
def calculate_reserve_rate(ma250, ma750):
    """计算预定利率研究值"""
    # 基础回报水平
    base_250 = ma250 + TAX_PREMIUM_250
    base_750 = ma750 + TAX_PREMIUM_750
    base_return = min(base_250, base_750)

    # 差值
    diff = REFERENCE_RATE - base_return

    # 系数调整
    # 根据差值查表
    if diff <= 0.01:
        adjustment = 0.01
    elif diff <= 0.02:
        adjustment = 0.01
    elif diff <= 0.025:
        # 线性插值
        adjustment = 0.01 + 0.95 * (diff - 0.02) / 0.005 * 0.00475
    elif diff <= 0.03:
        adjustment = 0
    else:
        adjustment = 0

    # 预定利率
    reserve_rate = base_return - adjustment

    return {
        'base_250': base_250,
        'base_750': base_750,
        'base_return': base_return,
        'diff': diff,
        'adjustment': adjustment,
        'reserve_rate': reserve_rate
    }

# 计算基础回报水平
df_bond['基础回报水平'] = df_bond.apply(
    lambda row: min(row['MA250'] + TAX_PREMIUM_250, row['MA750'] + TAX_PREMIUM_750)
    if pd.notna(row['MA250']) and pd.notna(row['MA750']) else np.nan, axis=1
)

# ============== 回溯验证 ==============
print("=" * 70)
print("各季度预测值 vs 实际值")
print("=" * 70)
print()

# 已知的实际预定利率研究值
actual_values = {
    '2024-12-31': 0.0234,  # 2.34% (2025年1月发布)
    '2025-03-31': 0.0213,  # 2.13% (2025年4月发布)
    '2025-06-30': 0.0199,  # 1.99% (2025年7月发布)
    '2025-09-30': 0.0190,  # 1.90% (2025年10月发布)
    '2025-12-31': 0.0189,  # 1.89% (2026年1月发布)
}

# 季度末日期（用于取数据）
quarter_dates = {
    '2024-Q4': '2024-12-31',
    '2025-Q1': '2025-03-31',
    '2025-Q2': '2025-06-30',
    '2025-Q3': '2025-09-30',
    '2025-Q4': '2025-12-31',
}

print("┌────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐")
print("│  季度      │  MA250   │  MA750   │ 基础回报 │  预测值  │  实际值  │  差异    │")
print("├────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤")

results = []

for quarter, date_str in quarter_dates.items():
    target_date = pd.to_datetime(date_str)

    # 找到最接近该日期的数据
    if target_date in df_bond['日期'].values:
        row = df_bond[df_bond['日期'] == target_date].iloc[0]
    else:
        # 找到最接近的日期
        idx = (df_bond['日期'] - target_date).abs().idxmin()
        row = df_bond.loc[idx]

    ma250 = row['MA250']
    ma750 = row['MA750']
    base_return = row['基础回报水平']

    if pd.notna(ma250) and pd.notna(ma750):
        # 计算预测值
        calc = calculate_reserve_rate(ma250, ma750)
        pred = calc['reserve_rate']

        # 获取实际值
        actual = actual_values.get(date_str, None)

        diff_str = ""
        diff_bp = 0
        if actual is not None:
            diff_val = pred - actual
            diff_bp = diff_val * 10000  # 转换为bp
            diff_str = f"{diff_val*100:+.2f}%"
            if abs(diff_bp) < 1:
                diff_str = f"{diff_bp:+.1f}BP"
            else:
                diff_str = f"{diff_bp:+.0f}BP"

        print(f"│ {quarter:10s} │ {ma250*100:7.4f}% │ {ma750*100:7.4f}% │ {base_return*100:7.4f}% │ {pred*100:7.4f}% │ {actual*100:7.4f}% │ {diff_str:>9s} │")

        results.append({
            'quarter': quarter,
            'date': date_str,
            'ma250': ma250,
            'ma750': ma750,
            'base_return': base_return,
            'predicted': pred,
            'actual': actual,
            'diff_bp': diff_bp
        })

print("└────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘")

# ============== 详细计算示例 ==============
print("\n" + "=" * 70)
print("详细计算示例: 2025年Q4 (站在2025-12-31预测)")
print("=" * 70)

# 使用2024-12-31的数据（因为Excel数据只到2024-12-31）
q4_data = df_bond[df_bond['日期'] == pd.to_datetime('2024-12-31')]
if len(q4_data) == 0:
    q4_data = df_bond[df_bond['日期'] <= pd.to_datetime('2025-12-31')].tail(1)

row = q4_data.iloc[0]
ma250 = row['MA250']
ma750 = row['MA750']
actual_date = row['日期']

print(f"\n【输入数据 (数据日期: {actual_date.date()})】")
print(f"- 10年期国债MA250: {ma250:.6f} ({ma250*100:.4f}%)")
print(f"- 10年期国债MA750: {ma750:.6f} ({ma750*100:.4f}%)")
print(f"- 10年期国债最新收益率: {row['10Y收益率']:.6f} ({row['10Y收益率']*100:.4f}%)")

print(f"""
【计算过程】
1. 基础回报水平 = Min(MA250 + 税收溢价, MA750 + 税收溢价)
   - MA250 + 税收溢价 = {ma250*100:.4f}% + {TAX_PREMIUM_250*100:.4f}% = {(ma250 + TAX_PREMIUM_250)*100:.4f}%
   - MA750 + 税收溢价 = {ma750*100:.4f}% + {TAX_PREMIUM_750*100:.4f}% = {(ma750 + TAX_PREMIUM_750)*100:.4f}%
   - 基础回报水平 = Min({(ma250 + TAX_PREMIUM_250)*100:.4f}%, {(ma750 + TAX_PREMIUM_750)*100:.4f}%) = {(min(ma250 + TAX_PREMIUM_250, ma750 + TAX_PREMIUM_750))*100:.4f}%

2. 参考利率 = {REFERENCE_RATE*100:.2f}%

3. 差值 = 参考利率 - 基础回报水平 = {REFERENCE_RATE*100:.2f}% - {min(ma250 + TAX_PREMIUM_250, ma750 + TAX_PREMIUM_750)*100:.4f}% = {(REFERENCE_RATE - min(ma250 + TAX_PREMIUM_250, ma750 + TAX_PREMIUM_750))*100:.4f}%

4. 系数调整 = 0 (因为差值为负，进入特殊处理区间)

5. 预定利率研究值 = 基础回报水平 - 系数调整 = {(min(ma250 + TAX_PREMIUM_250, ma750 + TAX_PREMIUM_750))*100:.4f}% - 0 = {(min(ma250 + TAX_PREMIUM_250, ma750 + TAX_PREMIUM_750))*100:.4f}%
""")

# 预测值
pred_value = min(ma250 + TAX_PREMIUM_250, ma750 + TAX_PREMIUM_750)
actual_q4 = 0.0189  # 1.89%

print(f"""【预测结果】
- 预测值: {pred_value*100:.2f}%
- 实际值: {actual_q4*100:.2f}%
- 差异:   {(pred_value - actual_q4)*100:.2f}% ({(pred_value - actual_q4)*10000:+.0f}BP)
""")

# ============== 误差分析 ==============
print("=" * 70)
print("误差分析")
print("=" * 70)
print()

# 计算平均误差
valid_results = [r for r in results if r['actual'] is not None]
if valid_results:
    avg_diff = np.mean([(r['predicted'] - r['actual']) * 10000 for r in valid_results])
    print(f"平均预测误差: {avg_diff:+.1f}BP")

    print("""
【预测偏差原因分析】

1. 数据时效性问题
   - 国债数据仅到2024-12-31
   - 2025年的利率变化无法纳入预测

2. 公式理解可能需要修正
   - 税收溢价参数可能不是固定的
   - 可能存在其他的平滑机制

3. 实际计算可能有不同的处理逻辑
   - 专家委员会可能根据市场情况调整
   - 可能采用不同的移动平均窗口

【建议】
- 获取2025年的完整国债收益率数据
- 深入研究Excel中的计算公式细节
- 与保险行业协会公开的计算方法对照
""")

# ============== 保存结果 ==============
print("\n" + "=" * 70)
print("预测数据汇总")
print("=" * 70)

# 保存到DataFrame
results_df = pd.DataFrame(results)
print(results_df.to_string(index=False))
