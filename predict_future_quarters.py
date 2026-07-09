import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta

print("=" * 70)
print("预定利率研究值预测 - 基于当前数据平推")
print("=" * 70)
print(f"预测生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================
# 1. 获取当前最新数据
# ============================================

# 1.1 10年期国债收益率日频数据
print("\n【1. 获取当前最新数据】")
df_bond = ak.bond_zh_us_rate()
df_bond['date'] = pd.to_datetime(df_bond['日期'])
df_bond['10y'] = pd.to_numeric(df_bond['中国国债收益率10年'], errors='coerce')
df_bond = df_bond.sort_values('date').reset_index(drop=True)

latest_bond_date = df_bond['date'].max()
latest_bond_yield = df_bond.iloc[-1]['10y']
print(f"  10年期国债收益率最新数据：{latest_bond_date.date()} = {latest_bond_yield:.4f}%")
print(f"  ⚠️ 预测假设：未来国债收益率也采用平推方法（保持当前水平不变）")

# 1.1.1 对国债收益率数据采用平推扩展（将当前收益率延展至未来）
# 创建未来日期的国债收益率数据（平推假设）
future_dates = pd.date_range(start=latest_bond_date + pd.Timedelta(days=1), end='2027-12-31', freq='B')  # 仅工作日
future_df = pd.DataFrame({
    'date': future_dates,
    '10y': latest_bond_yield
})
future_df['日期'] = future_df['date']  # 保持与原数据相同的列名
df_bond_extended = pd.concat([df_bond, future_df[['日期', 'date', '10y']]], ignore_index=True)
df_bond_extended = df_bond_extended.sort_values('date').reset_index(drop=True)
print(f"  扩展后数据范围：{df_bond_extended['date'].min().date()} 至 {df_bond_extended['date'].max().date()}")

# 1.2 当前LPR和定存利率（平推假设）
current_lpr = 3.50  # 2025-05-20起
current_deposit = 1.30  # 2025-05-20起

print(f"\n  当前5年期LPR：{current_lpr:.2f}% (自2025-05-20)")
print(f"  当前5年期定存利率：{current_deposit:.2f}% (自2025-05-20)")
print(f"  ⚠️ 预测假设：未来4个季度LPR和定存利率保持当前水平不变")

# 1.3 历史利差数据（继续使用2024年底近似值）
historical_spreads = {
    '250MA': {
        '国开-国债': 0.0912,
        '进出口-国债': 0.1386,
    },
    '750MA': {
        '国开-国债': 0.1380,
        '进出口-国债': 0.2224,
    },
}

# ============================================
# 2. 定义计算函数
# ============================================

def compute_ma_values(target_date, df_bond, ma_days=250):
    """计算指定日期前的MA"""
    target = pd.Timestamp(target_date)
    subset = df_bond[df_bond['date'] <= target].copy()
    if len(subset) < ma_days:
        return None
    ma = subset.tail(ma_days)['10y'].mean()
    return ma

def compute_reference_rate_flat(lpr, deposit, months):
    """计算参考利率（平推假设下，所有月份使用相同LPR和定存利率）"""
    values = []
    for year, month in months:
        values.append((lpr + deposit) / 2)
    return np.mean(values)

def compute_base_return(ma250, ma750, spreads):
    """计算基础回报水平"""
    tax_premium_250 = max(spreads['250MA']['国开-国债'], spreads['250MA']['进出口-国债'])
    tax_premium_750 = max(spreads['750MA']['国开-国债'], spreads['750MA']['进出口-国债'])
    
    total_250 = ma250 + tax_premium_250
    total_750 = ma750 + tax_premium_750
    base_return = min(total_250, total_750)
    
    return {
        'ma250_bond': ma250,
        'ma750_bond': ma750,
        'tax_premium_250': tax_premium_250,
        'tax_premium_750': tax_premium_750,
        'total_250': total_250,
        'total_750': total_750,
        'base_return': base_return,
    }

def calculate_coeff(pre_coeff):
    """分段系数调节"""
    segments = [
        (0.00, 1.00, 1.00),
        (1.00, 2.00, 1.00),
        (2.00, 2.50, 0.95),
        (2.50, 3.00, 0.95),
        (3.00, 3.50, 0.50),
        (3.50, 4.00, 0.50),
        (4.00, 10.00, 0.30),
    ]
    total = 0
    for low, high, coeff in segments:
        if pre_coeff > high:
            total += (high - low) * coeff
        elif pre_coeff > low:
            total += (pre_coeff - low) * coeff
        else:
            break
    return total

# ============================================
# 3. 预测未来4个季度
# ============================================

print("\n" + "=" * 70)
print("【未来4个季度预测】")
print("=" * 70)

# 定义未来4个季度
# 预定利率研究值在每个季度末计算，下季度初公布
future_quarters = {
    '2026Q3': {
        'comp_date': '2026-09-30',
        'months': [(2026, 4), (2026, 5), (2026, 6), (2026, 7), (2026, 8), (2026, 9)],
        'announce_date': '2026年10月',
    },
    '2026Q4': {
        'comp_date': '2026-12-31',
        'months': [(2026, 7), (2026, 8), (2026, 9), (2026, 10), (2026, 11), (2026, 12)],
        'announce_date': '2027年1月',
    },
    '2027Q1': {
        'comp_date': '2027-03-31',
        'months': [(2026, 10), (2026, 11), (2026, 12), (2027, 1), (2027, 2), (2027, 3)],
        'announce_date': '2027年4月',
    },
    '2027Q2': {
        'comp_date': '2027-06-30',
        'months': [(2027, 1), (2027, 2), (2027, 3), (2027, 4), (2027, 5), (2027, 6)],
        'announce_date': '2027年7月',
    },
}

results = {}

for q_name, q_info in future_quarters.items():
    print(f"\n{'─' * 70}")
    print(f"  预测季度：{q_name}")
    print(f"  计算日期：{q_info['comp_date']}")
    print(f"  公布时间：{q_info['announce_date']}")
    
    # 1. 计算参考利率（平推假设）
    ref_rate = compute_reference_rate_flat(current_lpr, current_deposit, q_info['months'])
    print(f"  参考利率计算窗口：{[f'{y}-{m:02d}' for y, m in q_info['months']]}")
    print(f"  ⚠️ 平推假设：所有月份LPR={current_lpr:.2f}%, 定存={current_deposit:.2f}%")
    print(f"  参考利率 = {ref_rate:.4f}%")
    
    # 2. 计算基础回报水平（使用扩展数据）
    comp_date = q_info['comp_date']
    ma250 = compute_ma_values(comp_date, df_bond_extended, 250)
    ma750 = compute_ma_values(comp_date, df_bond_extended, 750)
    
    if ma250 is None or ma750 is None:
        print(f"  ⚠️ 警告：{comp_date}前数据不足，无法计算MA")
        continue
    
    base = compute_base_return(ma250, ma750, historical_spreads)
    print(f"  10年期国债MA250 = {ma250:.4f}%")
    print(f"  10年期国债MA750 = {ma750:.4f}%")
    print(f"  税收溢价(250MA) = {base['tax_premium_250']:.4f}%")
    print(f"  税收溢价(750MA) = {base['tax_premium_750']:.4f}%")
    print(f"  250MA合计 = {base['total_250']:.4f}%")
    print(f"  750MA合计 = {base['total_750']:.4f}%")
    print(f"  基础回报水平 = MIN({base['total_250']:.4f}%, {base['total_750']:.4f}%) = {base['base_return']:.4f}%")
    
    # 3. 计算系数调节前
    pre_coeff = min(ref_rate, base['base_return'])
    print(f"  系数调节前 = MIN({ref_rate:.4f}%, {base['base_return']:.4f}%) = {pre_coeff:.4f}%")
    
    # 4. 计算最终预定利率
    final = calculate_coeff(pre_coeff)
    
    print(f"  ")
    print(f"  >>> 预测值 = {final:.4f}% = {final * 100:.2f}BP")
    
    results[q_name] = {
        'ref_rate': ref_rate,
        'ma250': ma250,
        'ma750': ma750,
        'base_return': base['base_return'],
        'pre_coeff': pre_coeff,
        'predicted': final,
        'announce_date': q_info['announce_date'],
    }

# ============================================
# 4. 汇总预测结果
# ============================================

print("\n" + "=" * 70)
print("【预测结果汇总】")
print("=" * 70)
print(f"{'季度':<10} {'公布时间':<12} {'预测值(%)':<12} {'参考利率(%)':<15} {'基础回报(%)':<15} {'说明':<20}")
print("-" * 70)

for q_name in future_quarters.keys():
    if q_name in results:
        r = results[q_name]
        print(f"{q_name:<10} {r['announce_date']:<12} {r['predicted']:<12.4f} {r['ref_rate']:<15.4f} {r['base_return']:<15.4f} {'平推假设':<20}")
    else:
        print(f"{q_name:<10} {'-':<12} {'数据不足':<12} {'-':<12} {'-':<12} {'-':<20}")

# ============================================
# 5. 敏感性分析：如果LPR或定存利率变化
# ============================================

print("\n" + "=" * 70)
print("【敏感性分析】假设LPR或定存利率变化的影响")
print("=" * 70)
print("说明：分析参考利率对各输入变量的敏感性")

# 分析2026Q3（第一个预测季度）
q_name = '2026Q3'
q_info = future_quarters[q_name]
ma250 = compute_ma_values(q_info['comp_date'], df_bond_extended, 250)
ma750 = compute_ma_values(q_info['comp_date'], df_bond_extended, 750)
base = compute_base_return(ma250, ma750, historical_spreads)
base_return = base['base_return']

print(f"\n基准情景（{q_name}）：")
print(f"  LPR = {current_lpr:.2f}%, 定存 = {current_deposit:.2f}%")
print(f"  参考利率 = {(current_lpr + current_deposit) / 2:.4f}%")
print(f"  基础回报水平 = {base_return:.4f}%")
pre_coeff_base = min((current_lpr + current_deposit) / 2, base_return)
final_base = calculate_coeff(pre_coeff_base)
print(f"  预测值 = {final_base*100:.4f}%")

print(f"\n敏感性分析：")
print(f"{'情景':<20} {'LPR':<8} {'定存':<8} {'参考利率':<12} {'预测值':<12} {'变化(BP)':<10}")
print("-" * 70)

scenarios = [
    ('基准情景', current_lpr, current_deposit),
    ('LPR下调10BP', current_lpr - 0.10, current_deposit),
    ('LPR下调20BP', current_lpr - 0.20, current_deposit),
    ('定存下调10BP', current_lpr, current_deposit - 0.10),
    ('定存下调20BP', current_lpr, current_deposit - 0.20),
    ('LPR+定存各下调10BP', current_lpr - 0.10, current_deposit - 0.10),
    ('LPR+定存各下调20BP', current_lpr - 0.20, current_deposit - 0.20),
]

for scenario, lpr, deposit in scenarios:
    ref_rate = (lpr + deposit) / 2
    pre_coeff = min(ref_rate, base_return)
    final = calculate_coeff(pre_coeff)
    change_bp = (final - final_base) * 100
    print(f"{scenario:<20} {lpr:<8.2f} {deposit:<8.2f} {ref_rate:<12.4f} {final*100:<12.4f} {change_bp:<10.1f}")

# ============================================
# 6. 生成预测报告
# ============================================

print("\n" + "=" * 70)
print("【预测结论】")
print("=" * 70)
print(f"\n基于当前数据平推假设（LPR={current_lpr:.2f}%, 定存={current_deposit:.2f}%），未来4个季度预测值：")

for q_name in future_quarters.keys():
    if q_name in results:
        r = results[q_name]
        print(f"  {q_name} ({r['announce_date']}公布)：{r['predicted']:.4f}%")

print("\n⚠️ 重要说明：")
print("  1. 本预测基于'平推'假设，即未来利率保持当前水平不变")
print("  2. 实际计算中，10年期国债收益率会继续变化（MA250/MA750会动态调整）")
print("  3. 若LPR或定存利率调整，预测值需相应更新")
print("  4. 信用债利差采用固定近似值，实际值可能有所偏差")
print("  5. 本预测仅供参靠，实际值以中国保险行业协会公布为准")

print("\n" + "=" * 70)
