"""
预定利率研究值预测脚本 - 修正版
方法：基于当前已公布值，预测未来4个季度
平推方法：对于未来无实际数据的日期，使用最后一天实际数平推

当前时间点：2026年7月2日
已公布值：2026Q1（1.93%）
需预测：2026Q2, 2026Q3, 2026Q4, 2027Q1
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import calendar

# ============================================================
# 配置参数
# ============================================================

# 分段系数调节表
SEGMENT_COEFF = [
    (0.00, 1.00, 1.00),
    (1.00, 2.00, 1.00),
    (2.00, 2.50, 0.95),
    (3.00, 3.50, 0.50),
    (3.50, 4.00, 0.50),
    (4.00, 10.00, 0.30),
]

# 当前最新实际数据（2026年7月2日）
CURRENT_DATE = '2026-07-02'
CURRENT_LPR = 3.50  # 5年期LPR（2025年5月20日起）
CURRENT_DEPOSIT = 1.30  # 六大行5年期定存利率（2025年5月20日起）
CURRENT_BOND_YIELD = 1.7410  # 10年期国债收益率（2026年7月2日）%

# 信用债利差近似值（2024年底数据）
SPREAD_250MA = {'国开-国债': 0.0912, '进出口-国债': 0.1386}
SPREAD_750MA = {'国开-国债': 0.1380, '进出口-国债': 0.2224}

# ============================================================
# 辅助函数
# ============================================================

def get_monthly_lpr(end_date):
    """
    获取指定日期所在月适用的5年期LPR
    使用月末日期判断（以捕捉月中调整）
    """
    lpr_history = [
        ('2023-06-20', 4.20),
        ('2024-02-20', 3.95),
        ('2024-07-22', 3.85),
        ('2024-10-21', 3.60),
        ('2025-05-20', 3.50),
    ]
    
    end_dt = pd.to_datetime(end_date)
    month_end = end_dt.replace(day=calendar.monthrange(end_dt.year, end_dt.month)[1])
    
    applicable_rate = lpr_history[0][1]
    for start_date, rate in lpr_history:
        if pd.to_datetime(start_date) <= month_end:
            applicable_rate = rate
    
    return applicable_rate

def get_monthly_deposit(end_date):
    """
    获取指定日期所在月适用的5年期定存利率
    使用月末日期判断
    """
    deposit_history = [
        ('2023-12-22', 2.00),
        ('2024-07-25', 1.80),
        ('2024-10-18', 1.55),
        ('2025-05-20', 1.30),
    ]
    
    end_dt = pd.to_datetime(end_date)
    month_end = end_dt.replace(day=calendar.monthrange(end_dt.year, end_dt.month)[1])
    
    applicable_rate = deposit_history[0][1]
    for start_date, rate in deposit_history:
        if pd.to_datetime(start_date) <= month_end:
            applicable_rate = rate
    
    return applicable_rate

def extend_bond_data(df_bond, current_date, future_date):
    """
    扩展国债收益率数据：对于future_date之后的日期，使用current_date的收益率平推
    """
    current_dt = pd.to_datetime(current_date)
    future_dt = pd.to_datetime(future_date)
    
    # 获取当前最新收益率
    latest_yield = df_bond[df_bond['date'] <= current_dt].iloc[-1]['10y']
    
    # 生成未来日期范围
    date_range = pd.date_range(start=current_dt + timedelta(days=1), end=future_dt, freq='B')  # 仅工作日
    
    if len(date_range) > 0:
        # 创建平推数据
        extend_df = pd.DataFrame({
            'date': date_range,
            '10y': latest_yield
        })
        
        # 合并数据
        df_extended = pd.concat([df_bond, extend_df], ignore_index=True)
        df_extended = df_extended.drop_duplicates(subset=['date'], keep='last')
        df_extended = df_extended.sort_values('date').reset_index(drop=True)
        
        return df_extended
    
    return df_bond

def compute_ma(df_bond, comp_date, window):
    """
    计算移动平均
    comp_date: 计算截止日期
    window: 窗口天数（250或750）
    """
    comp_dt = pd.to_datetime(comp_date)
    
    # 获取截止日期前的数据
    df_hist = df_bond[df_bond['date'] <= comp_dt].copy()
    
    if len(df_hist) < window:
        return np.nan
    
    # 取最近window个交易日
    recent_data = df_hist.tail(window)
    return recent_data['10y'].mean()

def apply_segment_adjustment(pre_adjustment):
    """
    应用分段系数调节
    """
    if pd.isna(pre_adjustment):
        return np.nan
    
    # 找到所在区间
    for low, high, coeff in SEGMENT_COEFF:
        if low < pre_adjustment <= high:
            return pre_adjustment * coeff
    
    return pre_adjustment

def calculate_predicted_value(comp_date, df_bond_extended):
    """
    计算指定计算日期的预定利率研究值
    """
    comp_dt = pd.to_datetime(comp_date)
    
    # 1. 计算参考利率（6个月移动平均）
    months = []
    for i in range(5, -1, -1):  # 前6个月
        year = comp_dt.year
        month = comp_dt.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))
    
    ref_rates = []
    for year, month in months:
        lpr = get_monthly_lpr(f'{year}-{month:02d}-01')
        deposit = get_monthly_deposit(f'{year}-{month:02d}-01')
        ref_rates.append((lpr + deposit) / 2)
    
    ref_rate = np.mean(ref_rates)
    
    # 2. 计算基础回报水平
    ma250 = compute_ma(df_bond_extended, comp_date, 250)
    ma750 = compute_ma(df_bond_extended, comp_date, 750)
    
    # 税收溢价（使用历史利差近似）
    tax_premium_250 = max(SPREAD_250MA['国开-国债'], SPREAD_250MA['进出口-国债'])
    tax_premium_750 = max(SPREAD_750MA['国开-国债'], SPREAD_750MA['进出口-国债'])
    
    base_return_250 = ma250 + tax_premium_250
    base_return_750 = ma750 + tax_premium_750
    base_return = min(base_return_250, base_return_750)
    
    # 3. 调整前利率
    pre_adjustment = min(ref_rate, base_return)
    
    # 4. 分段系数调节
    final_rate = apply_segment_adjustment(pre_adjustment)
    
    return {
        'ref_rate': ref_rate,
        'base_return': base_return,
        'ma250': ma250,
        'ma750': ma750,
        'pre_adjustment': pre_adjustment,
        'predicted': final_rate
    }

# ============================================================
# 主程序
# ============================================================

def main():
    print("=" * 70)
    print("预定利率研究值预测 - 修正版")
    print("=" * 70)
    
    # 1. 获取10年期国债收益率数据
    print("\n【1. 获取国债收益率数据】")
    df_bond = ak.bond_zh_us_rate()
    df_bond['date'] = pd.to_datetime(df_bond['日期'])
    df_bond['10y'] = pd.to_numeric(df_bond['中国国债收益率10年'], errors='coerce')
    df_bond = df_bond.sort_values('date').reset_index(drop=True)
    
    latest_bond_date = df_bond['date'].max()
    latest_bond_yield = df_bond.iloc[-1]['10y']
    print(f"  最新数据：{latest_bond_date.date()} = {latest_bond_yield:.4f}%")
    
    # 2. 定义需要预测的季度
    print("\n【2. 预测未来4个季度】")
    print("  当前时间点：2026年7月2日")
    print("  已公布值：2026Q1（1.93%）")
    print("  需预测：2026Q2, 2026Q3, 2026Q4, 2027Q1\n")
    
    future_quarters = {
        '2026Q2': {
            'comp_date': '2026-06-30',  # 计算截止日期
            'announce_date': '2026-07',  # 公布时间
            'description': '2026年二季度'
        },
        '2026Q3': {
            'comp_date': '2026-09-30',
            'announce_date': '2026-10',
            'description': '2026年三季度'
        },
        '2026Q4': {
            'comp_date': '2026-12-31',
            'announce_date': '2027-01',
            'description': '2026年四季度'
        },
        '2027Q1': {
            'comp_date': '2027-03-31',
            'announce_date': '2027-04',
            'description': '2027年一季度'
        }
    }
    
    results = {}
    
    for q_name, q_info in future_quarters.items():
        comp_date = q_info['comp_date']
        
        # 扩展国债数据（平推）
        df_extended = extend_bond_data(df_bond, CURRENT_DATE, comp_date)
        
        # 计算预测值
        result = calculate_predicted_value(comp_date, df_extended)
        results[q_name] = result
        
        print(f"{q_name} ({q_info['description']})")
        print(f"  计算截止日期：{comp_date}")
        print(f"  参考利率：{result['ref_rate']:.4f}%")
        print(f"  基础回报水平：{result['base_return']:.4f}% (MA250={result['ma250']:.4f}%, MA750={result['ma750']:.4f}%)")
        print(f"  调整前利率：{result['pre_adjustment']:.4f}%")
        print(f"  预测值：{result['predicted']:.4f}%")
        print()
    
    # 3. 汇总结果
    print("=" * 70)
    print("【汇总结果】")
    print("=" * 70)
    print(f"\n{'季度':<10} {'公布时间':<12} {'预测值(%)':<12} {'参考利率(%)':<14} {'基础回报(%)':<14}")
    print("-" * 70)
    
    for q_name, q_info in future_quarters.items():
        if q_name in results:
            r = results[q_name]
            # 注意：r['predicted']等已经是百分比格式（如1.9383表示1.9383%），不需要再乘以100
            print(f"{q_name:<10} {q_info['announce_date']:<12} {r['predicted']:<12.4f} {r['ref_rate']:<14.4f} {r['base_return']:<14.4f}")
    
    print("\n" + "=" * 70)
    print("【预测结论】")
    print("=" * 70)
    
    base_predicted = results['2026Q2']['predicted'] * 100
    print(f"\n基于当前数据平推假设（截至{CURRENT_DATE}），未来4个季度预测值：")
    print()
    
    for q_name, q_info in future_quarters.items():
        if q_name in results:
            r = results[q_name]
            predicted_pct = r['predicted']  # 已经是百分比格式
            
            if q_name == '2026Q2':
                change = 0
            else:
                prev_q = list(future_quarters.keys())[list(future_quarters.keys()).index(q_name) - 1]
                prev_predicted = results[prev_q]['predicted']
                change = (predicted_pct - prev_predicted) * 100  # 转换为BP
            
            print(f"  {q_name} ({q_info['announce_date']}公布)：{predicted_pct:.4f}% (变化：{change:+.2f} BP)")
    
    # 4. 触发分析
    print("\n" + "=" * 70)
    print("【调整触发分析】")
    print("=" * 70)
    
    # 配置
    MAX_RATE = 2.00  # 当前普通型保险产品预定利率最高值（2025年9月1日起生效）
    TRIGGER_THRESHOLD = 0.25  # 25 BP
    
    # 历史数据：实际公布的研究值
    historical_research = {
        '2024Q4': 2.34,
        '2025Q1': 2.13,
        '2025Q2': 1.99,
        '2025Q3': 1.90,
        '2025Q4': 1.89,
        '2026Q1': 1.93,
    }
    
    print(f"\n当前普通型保险产品预定利率最高值：{MAX_RATE:.2f}%")
    print(f"触发阈值：{TRIGGER_THRESHOLD*100:.0f} BP")
    print(f"\n{'季度':<10} {'研究值(%)':<12} {'最高值(%)':<12} {'差值(BP)':<12} {'状态':<15} {'是否触发':<15}")
    print("-" * 75)
    
    # 先展示历史
    last_historical_trigger_q = None
    for q_name, rv in historical_research.items():
        # Determine max rate for this quarter
        if q_name <= '2025Q2':
            q_max_rate = 2.50
        else:
            q_max_rate = 2.00
        
        gap_bp = round((q_max_rate - rv) * 100, 1)
        
        if gap_bp >= 25:
            status = f"⚠️ 差值≥{TRIGGER_THRESHOLD*100:.0f}BP"
            triggered = "是(历史触发)"
            last_historical_trigger_q = q_name
        else:
            status = "差值不足"
            triggered = "否"
        
        print(f"{q_name:<10} {rv:<12.2f} {q_max_rate:<12.2f} {gap_bp:<12.1f} {status:<15} {triggered:<15}")
    
    # 再展示预测
    print(f"\n--- 以下为预测值 ---")
    consecutive_trigger_count = 0
    for q_name, q_info in future_quarters.items():
        if q_name in results:
            r = results[q_name]
            rv = r['predicted']
            gap_bp = round((MAX_RATE - rv) * 100, 1)
            
            if gap_bp >= 25:
                consecutive_trigger_count += 1
                status = f"⚠️ 差值≥{TRIGGER_THRESHOLD*100:.0f}BP"
            else:
                consecutive_trigger_count = 0
                status = "差值不足"
            
            if consecutive_trigger_count >= 2:
                triggered = "🔴 触发下调！"
            else:
                triggered = "否"
            
            print(f"{q_name:<10} {rv:<12.4f} {MAX_RATE:<12.2f} {gap_bp:<12.1f} {status:<15} {triggered:<15}")
    
    print(f"\n分析结论：")
    print(f"  基于当前预测，未来4个季度最高值与研究值的差值最大为 {round((MAX_RATE - results['2027Q1']['predicted']) * 100, 1)} BP（{list(future_quarters.keys())[-1]}），")
    print(f"  远低于{TRIGGER_THRESHOLD*100:.0f}BP的触发阈值，预计未来4个季度均不触发预定利率调整。")
    print(f"  要触发下调，需研究值降至{MAX_RATE - TRIGGER_THRESHOLD:.2f}%以下（且连续2个季度）。")
    print(f"  要触发上调，需研究值升至{MAX_RATE + TRIGGER_THRESHOLD:.2f}%以上（且连续2个季度）。")
    
    # 5. 保存结果
    print("\n" + "=" * 70)
    print("【保存结果】")
    print("=" * 70)
    
    output_data = []
    for q_name, q_info in future_quarters.items():
        if q_name in results:
            r = results[q_name]
            gap_bp = round((2.00 - r['predicted']) * 100, 1)
            output_data.append({
                '季度': q_name,
                '公布时间': q_info['announce_date'],
                '预测值(%)': round(r['predicted'], 4),
                '参考利率(%)': round(r['ref_rate'], 4),
                '基础回报水平(%)': round(r['base_return'], 4),
                'MA250(%)': round(r['ma250'], 4),
                'MA750(%)': round(r['ma750'], 4),
                '最高值(%)': 2.00,
                '差值(BP)': gap_bp,
                '触发状态': '否' if gap_bp < 25 else '是'
            })
    
    df_output = pd.DataFrame(output_data)
    output_file = 'future_prediction_corrected.csv'
    df_output.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存到：{output_file}")
    
    return results

if __name__ == '__main__':
    results = main()
