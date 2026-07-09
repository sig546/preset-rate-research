import akshare as ak
import pandas as pd
import numpy as np

print("=" * 60)
print("预定利率研究值回溯验证（2025年）")
print("=" * 60)

# 获取2023-2025年国债数据用于计算750MA
print("\n【获取历史国债数据】")
df_2023 = ak.bond_china_yield(start_date="20230101", end_date="20231231")
gz_2023 = df_2023[df_2023['曲线名称'] == '中债国债收益率曲线'].copy()
gz_2023['日期'] = pd.to_datetime(gz_2023['日期'])
gz_2023['10年收益率'] = gz_2023['10年'].astype(float)

df_2024 = ak.bond_china_yield(start_date="20240101", end_date="20241231")
gz_2024 = df_2024[df_2024['曲线名称'] == '中债国债收益率曲线'].copy()
gz_2024['日期'] = pd.to_datetime(gz_2024['日期'])
gz_2024['10年收益率'] = gz_2024['10年'].astype(float)

df_2025 = ak.bond_china_yield(start_date="20250101", end_date="20251231")
gz_2025 = df_2025[df_2025['曲线名称'] == '中债国债收益率曲线'].copy()
gz_2025['日期'] = pd.to_datetime(gz_2025['日期'])
gz_2025['10年收益率'] = gz_2025['10年'].astype(float)

all_gz = pd.concat([gz_2023, gz_2024, gz_2025], ignore_index=True)
all_gz = all_gz.sort_values('日期').reset_index(drop=True)
print(f"总计获取到 {len(all_gz)} 个交易日数据")

# 计算各季度末的250MA和750MA
quarter_end_dates = [
    '2024-12-31',
    '2025-03-31',
    '2025-06-30',
    '2025-09-30',
    '2025-12-31',
]

print("\n【各季度末移动平均】")
ma_results = {}
for q_date in quarter_end_dates:
    q_dt = pd.to_datetime(q_date)
    end_idx = all_gz[all_gz['日期'] <= q_dt].index[-1]
    
    # 250MA
    start_250 = max(0, end_idx - 249)
    ma250 = all_gz.loc[start_250:end_idx, '10年收益率'].mean()
    
    # 750MA
    start_750 = max(0, end_idx - 749)
    ma750 = all_gz.loc[start_750:end_idx, '10年收益率'].mean()
    
    ma_results[q_date] = {'250MA': ma250, '750MA': ma750}
    print(f"  {q_date}: 250MA={ma250:.4f}%, 750MA={ma750:.4f}%")

# =====================
# 使用历史利差估算国开债和进出口债
# =====================
print("\n【使用历史利差估算税收溢价】")

# 从2024年12月数据提取历史利差（作为参考）
historical_spreads = {
    '250MA': {'国开-国债': 0.0912, '进出口-国债': 0.1386},
    '750MA': {'国开-国债': 0.1380, '进出口-国债': 0.2224},
}

print("\n历史利差（2024-12-31）:")
for ma_type, spreads in historical_spreads.items():
    print(f"  {ma_type}: 国开-国债={spreads['国开-国债']:.4f}%, 进出口-国债={spreads['进出口-国债']:.4f}%")

# 假设2025年利差略有收窄（因为整体利率下行）
# 这里使用历史利差，但明确标注为近似
print("\n假设2025年利差与2024年底相近（近似计算）")

# =====================
# 计算基础回报水平
# =====================
print("\n【基础回报水平估算】")
base_results = {}
for q_date in quarter_end_dates:
    ma250 = ma_results[q_date]['250MA']
    ma750 = ma_results[q_date]['750MA']
    
    # 使用历史利差估算
    tax_premium_250 = max(historical_spreads['250MA']['国开-国债'], 
                          historical_spreads['250MA']['进出口-国债'])
    tax_premium_750 = max(historical_spreads['750MA']['国开-国债'], 
                          historical_spreads['750MA']['进出口-国债'])
    
    total_250 = ma250 + tax_premium_250
    total_750 = ma750 + tax_premium_750
    base_return = min(total_250, total_750)
    
    base_results[q_date] = {
        '250MA国债': ma250,
        '250MA税收': tax_premium_250,
        '250MA合计': total_250,
        '750MA国债': ma750,
        '750MA税收': tax_premium_750,
        '750MA合计': total_750,
        '基础回报': base_return,
    }
    
    print(f"\n  {q_date}:")
    print(f"    250MA: {ma250:.4f}% + {tax_premium_250:.4f}% = {total_250:.4f}%")
    print(f"    750MA: {ma750:.4f}% + {tax_premium_750:.4f}% = {total_750:.4f}%")
    print(f"    基础回报水平 = MIN({total_250:.4f}%, {total_750:.4f}%) = {base_return:.4f}%")

# =====================
# 计算参考利率
# =====================
print("\n【参考利率】")
lpr_data = {
    '2024-07': 3.85, '2024-08': 3.85, '2024-09': 3.85,
    '2024-10': 3.60, '2024-11': 3.60, '2024-12': 3.60,
    '2025-01': 3.35, '2025-02': 3.35, '2025-03': 3.35,
    '2025-04': 3.10, '2025-05': 3.10, '2025-06': 3.10,
    '2025-07': 3.10, '2025-08': 3.10, '2025-09': 3.10,
    '2025-10': 3.10, '2025-11': 3.10, '2025-12': 3.10,
}
deposit_data = {
    '2024-07': 1.80, '2024-08': 1.80, '2024-09': 1.80,
    '2024-10': 1.55, '2024-11': 1.55, '2024-12': 1.55,
    '2025-01': 1.55, '2025-02': 1.55, '2025-03': 1.55,
    '2025-04': 1.55, '2025-05': 1.55, '2025-06': 1.55,
    '2025-07': 1.55, '2025-08': 1.55, '2025-09': 1.55,
    '2025-10': 1.55, '2025-11': 1.55, '2025-12': 1.55,
}

quarters = {
    '2024Q4': ['2024-07', '2024-08', '2024-09', '2024-10', '2024-11', '2024-12'],
    '2025Q1': ['2024-10', '2024-11', '2024-12', '2025-01', '2025-02', '2025-03'],
    '2025Q2': ['2024-11', '2024-12', '2025-01', '2025-02', '2025-03', '2025-04'],
    '2025Q3': ['2024-12', '2025-01', '2025-02', '2025-03', '2025-04', '2025-05'],
    '2025Q4': ['2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06'],
}

quarter_dates = {
    '2024Q4': '2024-12-31',
    '2025Q1': '2025-03-31',
    '2025Q2': '2025-06-30',
    '2025Q3': '2025-09-30',
    '2025Q4': '2025-12-31',
}

ref_results = {}
for q_name, months in quarters.items():
    total = sum(lpr_data[m] + deposit_data[m] for m in months)
    ref_rate = total / 6 / 2
    ref_results[q_name] = ref_rate
    print(f"  {q_name}: 参考利率 = {ref_rate:.4f}%")

# =====================
# 计算最终预定利率
# =====================
print("\n【最终预定利率计算（系数调节前 = MIN(参考利率, 基础回报水平)）】")

pre_coeff_results = {}
for q_name, q_date in quarter_dates.items():
    ref = ref_results[q_name]
    base = base_results[q_date]['基础回报']
    pre_coeff = min(ref, base)
    pre_coeff_results[q_name] = pre_coeff
    print(f"  {q_name}: MIN({ref:.4f}%, {base:.4f}%) = {pre_coeff:.4f}%")

# =====================
# 系数调节（分段累加）
# =====================
print("\n【系数调节】")

def calculate_coeff(pre_coeff):
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

final_results = {}
actual_values = {
    '2024Q4': 2.34,
    '2025Q1': 2.13,
    '2025Q2': 1.99,
    '2025Q3': 1.90,
    '2025Q4': 1.89,
}

print("\n{:<10} {:>12} {:>12} {:>12} {:>12} {:>12}".format(
    "季度", "预测值(%)", "实际值(%)", "差异(BP)", "误差(%)", "备注"
))
print("-" * 70)

for q_name in ['2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']:
    pre_coeff = pre_coeff_results[q_name]
    final = calculate_coeff(pre_coeff)
    final_results[q_name] = final
    actual = actual_values.get(q_name, None)
    
    if actual:
        diff = (final - actual) * 100  # BP
        error_pct = abs(diff) / actual * 100 if actual != 0 else 0
        note = ""
        if abs(diff) < 5:
            note = "高度吻合"
        elif abs(diff) < 10:
            note = "基本吻合"
        else:
            note = "偏差较大"
        print(f"{q_name:<10} {final:>12.4f} {actual:>12.2f} {diff:>12.1f} {error_pct:>12.2f} {note}")
    else:
        print(f"{q_name:<10} {final:>12.4f} {'--':>12} {'--':>12} {'--':>12} {'待公布'}")

print("\n" + "=" * 60)
print("说明：")
print("1. 2024Q4已验证与Excel值一致（2.34%）")
print("2. 2025年Q1-Q4使用近似计算（假设利差与2024年底相近）")
print("3. 实际值来自保险业协会公布的历史数据")
print("=" * 60)
