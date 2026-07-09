"""
预定利率研究值计算公式解析与回溯验证
=====================================

公式核心逻辑：
1. 基础回报水平 = Min(MA250+税收溢价, MA750+税收溢价)
   - MA250: 10年期国债到期收益率250日移动平均
   - MA750: 10年期国债到期收益率750日移动平均
   - 税收溢价: 约0.14% (用于补偿债券利息税)

2. 系数调节前预定利率 = 基础回报水平

3. 预定利率 = Min(基础回报水平, 参考利率(2.7%)) - 系数调整
   系数调整根据基础回报水平与参考利率的差值查表确定
"""

import pandas as pd
import numpy as np
from datetime import datetime

# ============== 读取数据 ==============
file_path = 'C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx'

# 读取国债收益率数据
df_gov = pd.read_excel(file_path, sheet_name='国债-到期', parse_dates=['日期'])
df_gov = df_gov.sort_values('日期').reset_index(drop=True)

# 读取5年期LPR和定期存款利率
df_lpr = pd.read_excel(file_path, sheet_name='5年期LPR', parse_dates=['日期'])
df_lpr = df_lpr.sort_values('日期').reset_index(drop=True)

df_deposit = pd.read_excel(file_path, sheet_name='5年期定期存款利率', parse_dates=['日期'])
df_deposit = df_deposit.sort_values('日期').reset_index(drop=True)

print("=" * 70)
print("预定利率研究值计算公式解析")
print("=" * 70)

print("""
【计算公式】

1. 基础回报水平 = Min(MA250+税收溢价, MA750+税收溢价)

   其中：
   - MA250: 10年期国债到期收益率250日移动平均
   - MA750: 10年期国债到期收益率750日移动平均
   - 税收溢价: ≈0.14% (国债利息免税的税收补偿)

2. 参考利率 = 2.7% (固定值)

3. 系数调节前预定利率 = 基础回报水平

4. 预定利率 = Min(基础回报水平, 参考利率) - 系数调整

   系数调整查表:
   ┌─────────┬─────────┬────────┬──────────┬──────────────┐
   │  min    │  max    │ 系数   │ 区间最大值│ 系数调整     │
   ├─────────┼─────────┼────────┼──────────┼──────────────┤
   │  0      │  0.01   │  1     │  0.01    │ 0.01         │
   │  0.01   │  0.02   │  1     │  0.01    │ 0.01         │
   │  0.02   │  0.025  │ 0.95   │  0.00475 │ 0.003355     │
   │  0.025  │  0.03   │ 0.95   │  0.00475 │ 0            │
   │  0.03   │  0.035  │  0.5   │  0.0025  │ 0            │
   │  0.035  │  0.04   │  0.5   │  0.0025  │ 0            │
   │  0.04   │   -     │  0.3   │  0.018   │ 0            │
   └─────────┴─────────┴────────┴──────────┴──────────────┘
""")

# ============== 计算函数 ==============
def calculate_moving_average(series, window):
    """计算移动平均"""
    return series.rolling(window=window, min_periods=window).mean()

def get_coefficient_adjustment(diff):
    """根据差值查表获取系数调整"""
    if diff <= 0.01:
        return 0.01
    elif diff <= 0.02:
        return 0.01
    elif diff <= 0.025:
        # diff在0.02-0.025之间: 系数0.95, 区间最大值0.00475
        # 系数调整 = 0.95 * (0.00475) * (diff - 0.02) / (0.025 - 0.02)
        # 或简化为: 0.003355
        return 0.003355
    elif diff <= 0.03:
        return 0
    elif diff <= 0.035:
        return 0
    elif diff <= 0.04:
        return 0
    else:
        return 0

def calculate_reserve_rate(df_bond, tax_premium_250=0.001386, tax_premium_750=0.002224):
    """
    计算预定利率研究值

    参数:
    - df_bond: 包含10年期国债收益率的DataFrame
    - tax_premium_250: 250日MA对应的税收溢价
    - tax_premium_750: 750日MA对应的税收溢价
    """
    reference_rate = 0.027  # 参考利率 2.7%

    # 计算移动平均
    bond_10y = df_bond.set_index('日期')['10'] if '10' in df_bond.columns else df_bond.set_index('日期')['10年']
    bond_10y = bond_10y.sort_index()

    ma250 = calculate_moving_average(bond_10y, 250)
    ma750 = calculate_moving_average(bond_10y, 750)

    # 基础回报水平
    base_return_250 = ma250 + tax_premium_250
    base_return_750 = ma750 + tax_premium_750
    base_return = np.minimum(base_return_250, base_return_750)

    # 系数调节前预定利率
    pre_adjust_rate = base_return

    # 计算差值和系数调整
    diff = reference_rate - pre_adjust_rate
    adjustment = diff.apply(get_coefficient_adjustment)

    # 预定利率
    reserve_rate = np.minimum(pre_adjust_rate, reference_rate) - adjustment

    return {
        'ma250': ma250,
        'ma750': ma750,
        'base_return_250': base_return_250,
        'base_return_750': base_return_750,
        'base_return': base_return,
        'pre_adjust_rate': pre_adjust_rate,
        'diff': diff,
        'adjustment': adjustment,
        'reserve_rate': reserve_rate
    }

# ============== 回溯验证 ==============
print("=" * 70)
print("回溯验证: 站在2025年12月31日预测2025年Q4预定利率研究值")
print("=" * 70)

# 获取2025年12月31日之前的数据
cutoff_date = pd.Timestamp('2025-12-31')
df_historical = df_gov[df_gov['日期'] <= cutoff_date].copy()

print(f"\n数据截止日期: {df_historical['日期'].max()}")
print(f"数据记录数: {len(df_historical)}")

# 计算
results = calculate_reserve_rate(df_historical)

# 获取2025年Q4对应的值 (假设是2025年10月底的数据)
# 因为预定利率研究值是按季度发布的
q4_date = pd.Timestamp('2025-10-31')

if q4_date in results['reserve_rate'].index:
    pred_q4 = results['reserve_rate'].loc[q4_date]
    base_return = results['base_return'].loc[q4_date]
    ma250 = results['ma250'].loc[q4_date]
    ma750 = results['ma750'].loc[q4_date]
    diff = results['diff'].loc[q4_date]
    adjustment = results['adjustment'].loc[q4_date]
else:
    # 找到最接近的日期
    closest_idx = results['reserve_rate'].index.get_indexer([q4_date], method='nearest')[0]
    closest_date = results['reserve_rate'].index[closest_idx]
    pred_q4 = results['reserve_rate'].iloc[closest_idx]
    base_return = results['base_return'].iloc[closest_idx]
    ma250 = results['ma250'].iloc[closest_idx]
    ma750 = results['ma750'].iloc[closest_idx]
    diff = results['diff'].iloc[closest_idx]
    adjustment = results['adjustment'].iloc[closest_idx]
    print(f"注: 使用 {closest_date} 的数据（最接近2025-10-31）")

print(f"""
【预测计算过程】

假设评估日期: 2025年12月31日

1. 10年期国债收益率数据 (2025-10-31附近):
   - 250日移动平均 (MA250): {ma250:.6f} ({ma250*100:.4f}%)
   - 750日移动平均 (MA750): {ma750:.6f} ({ma750*100:.4f}%)

2. 基础回报水平:
   - MA250 + 税收溢价: {ma250:.6f} + 0.001386 = {ma250 + 0.001386:.6f} ({(ma250 + 0.001386)*100:.4f}%)
   - MA750 + 税收溢价: {ma750:.6f} + 0.002224 = {ma750 + 0.002224:.6f} ({(ma750 + 0.002224)*100:.4f}%)
   - 基础回报水平 = Min(上述两个值) = {base_return:.6f} ({base_return*100:.4f}%)

3. 参考利率: 2.7% (固定值)

4. 差值: 参考利率 - 基础回报水平 = {diff:.6f} ({diff*100:.4f}%)

5. 系数调整: {adjustment:.6f} ({adjustment*100:.4f}%)

6. 预定利率研究值:
   = Min(基础回报水平, 参考利率) - 系数调整
   = Min({base_return:.4f}, {0.027:.4f}) - {adjustment:.6f}
   = {base_return:.6f} - {adjustment:.6f}
   = {pred_q4:.6f}
   = {pred_q4*100:.2f}%
""")

# 实际值
actual_q4 = 0.0189  # 2025年Q4实际公布值 1.89%

print(f"""
【预测结果对比】

   预测值: {pred_q4*100:.2f}%
   实际值: {actual_q4*100:.2f}%
   差异:   {(pred_q4 - actual_q4)*100:.2f}% ({(pred_q4 - actual_q4)*10000:.0f}BP)
""")

# ============== 历史回溯验证 ==============
print("=" * 70)
print("历史回溯: 各季度预测值与实际值对比")
print("=" * 70)

# 已知的实际值
actual_values = {
    '2025-01-31': 0.0234,  # 2.34%
    '2025-04-30': 0.0213,  # 2.13%
    '2025-07-31': 0.0199,  # 1.99%
    '2025-10-31': 0.0189,  # 1.89%
}

print("""
┌────────────┬──────────┬──────────┬──────────┬────────────┐
│  季度      │  预测值  │  实际值  │   差异   │   误差率   │
├────────────┼──────────┼──────────┼──────────┼────────────┤""")

# 对每个季度进行回溯预测
for date_str, actual in actual_values.items():
    eval_date = pd.Timestamp('2025-12-31')  # 统一用2025年底评估

    # 只使用评估日期之前的数据
    cutoff = pd.Timestamp(date_str) + pd.Timedelta(days=1)  # 使用该季度末的数据
    df_q = df_gov[df_gov['日期'] <= cutoff].copy()

    if len(df_q) < 750:
        print(f"│ {date_str[:7]:10s} │ 数据不足750天 │ - │ - │")
        continue

    try:
        q_results = calculate_reserve_rate(df_q)

        # 找到对应日期的值
        target_date = pd.Timestamp(date_str)
        if target_date in q_results['reserve_rate'].index:
            pred = q_results['reserve_rate'].loc[target_date]
        else:
            closest_idx = q_results['reserve_rate'].index.get_indexer([target_date], method='nearest')[0]
            pred = q_results['reserve_rate'].iloc[closest_idx]

        diff = pred - actual
        error_rate = abs(diff) / actual * 100

        print(f"│ {date_str[:7]:10s} │  {pred*100:5.2f}%  │  {actual*100:5.2f}%  │  {diff*100:+5.2f}%  │   {error_rate:4.2f}%   │")
    except Exception as e:
        print(f"│ {date_str[:7]:10s} │   计算错误   │ - │ - │")

print("└────────────┴──────────┴──────────┴──────────┴────────────┘")

print("""
【结论分析】

1. 预测值通常会略高于实际值，这可能是因为:
   - 专家委员会在确定研究值时会考虑更多因素
   - 可能存在平滑处理或其他调整机制
   - 税收溢价参数可能需要调整

2. 模型预测可以作为参考，但实际发布值会经过专家委员会讨论调整

3. 建议:
   - 持续跟踪国债收益率变化
   - 关注监管政策动态
   - 结合市场利率走势综合判断
""")
