import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime

print("=" * 70)
print("预定利率研究值计算 - 基于公开数据源")
print("=" * 70)

# ============================================
# 1. 获取公开数据源
# ============================================

# 1.1 10年期国债收益率日频数据 (来源：中国货币网，通过akshare接口)
print("\n【1. 获取10年期国债收益率日频数据】")
print("来源：中国货币网 (www.shibor.net.cn / www.chinamoney.com.cn) via akshare")

df_bond = ak.bond_zh_us_rate()
df_bond['date'] = pd.to_datetime(df_bond['日期'])
df_bond['10y'] = pd.to_numeric(df_bond['中国国债收益率10年'], errors='coerce')
df_bond = df_bond.sort_values('date').reset_index(drop=True)
print(f"  数据范围：{df_bond['date'].min().date()} 至 {df_bond['date'].max().date()}")
print(f"  总记录数：{len(df_bond)}")

# 1.2 定义5年期LPR历史数据 (来源：中国货币网 www.shibor.net.cn)
print("\n【2. 5年期LPR历史数据】")
print("来源：中国货币网 (www.shibor.net.cn) 及 bendibao.com 历史数据汇总")

# LPR变更历史 (5年期以上)
# 数据整理自中国货币网公开历史数据
lpr_history = [
    ('2023-06-20', 4.20),  # 下调10bp
    ('2024-02-20', 3.95),  # 下调25bp
    ('2024-07-22', 3.85),  # 下调10bp
    ('2024-10-21', 3.60),  # 下调25bp
    ('2025-05-20', 3.50),  # 下调10bp (bendibao数据显示)
]

# 构建月度LPR数据 (使用月末生效利率)
def get_monthly_lpr(year, month):
    """获取指定月份的5年期LPR值 (使用月末生效利率)"""
    # 使用月末最后一天来确定该月适用的利率
    if month == 12:
        date = pd.Timestamp(f'{year+1}-01-01') - pd.Timedelta(days=1)
    else:
        date = pd.Timestamp(f'{year}-{month+1:02d}-01') - pd.Timedelta(days=1)
    current_rate = 4.30  # 初始值 (2023-06-20前为4.30)
    for change_date, rate in lpr_history:
        if date >= pd.Timestamp(change_date):
            current_rate = rate
    return current_rate

# 1.3 定义5年期定期存款利率 (来源：六大行官网公告)
print("\n【3. 六大行5年期定期存款利率】")
print("来源：工商银行、农业银行、中国银行、建设银行、交通银行、邮储银行官网公告")

# 存款利率变更历史 (6大行统一挂牌利率)
deposit_history = [
    ('2023-12-22', 2.00),  # 下调25bp
    ('2024-07-25', 1.80),  # 下调20bp
    ('2024-10-18', 1.55),  # 下调25bp
    ('2025-05-20', 1.30),  # 下调25bp
]

def get_monthly_deposit(year, month):
    """获取指定月份的5年期定存利率 (使用月末生效利率)"""
    if month == 12:
        date = pd.Timestamp(f'{year+1}-01-01') - pd.Timedelta(days=1)
    else:
        date = pd.Timestamp(f'{year}-{month+1:02d}-01') - pd.Timedelta(days=1)
    current_rate = 2.25  # 初始值 (2023-12-22前为2.25%)
    for change_date, rate in deposit_history:
        if date >= pd.Timestamp(change_date):
            current_rate = rate
    return current_rate

# 显示2024-2025年各月LPR和存款利率
print("\n  2024-2025年各月数据：")
print(f"  {'月份':<12} {'5Y-LPR':<10} {'5Y定存':<10} {'(LPR+定存)/2':<12}")
for year in [2024, 2025]:
    for month in range(1, 13):
        lpr = get_monthly_lpr(year, month)
        dep = get_monthly_deposit(year, month)
        avg = (lpr + dep) / 2
        print(f"  {year}-{month:02d}       {lpr:<10.2f} {dep:<10.2f} {avg:<12.4f}")

# 1.4 历史利差数据 (来源：Excel文件，因国开债/进出口债日频数据无公开渠道)
print("\n【4. 国开债/进出口债利差 (历史近似值)】")
print("说明：国开债和进出口债日频数据未在公开渠道获取")
print("采用2024年底Excel中列示的历史利差作为近似值")

# 2024-12-31 的利差数据 (来自Excel '预定利率' sheet)
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

print(f"  250MA利差：国开-国债 = {historical_spreads['250MA']['国开-国债']:.4f}%")
print(f"             进出口-国债 = {historical_spreads['250MA']['进出口-国债']:.4f}%")
print(f"  750MA利差：国开-国债 = {historical_spreads['750MA']['国开-国债']:.4f}%")
print(f"             进出口-国债 = {historical_spreads['750MA']['进出口-国债']:.4f}%")

# ============================================
# 2. 计算公式核心函数
# ============================================

def compute_ma_values(target_date, df_bond, ma_days=250):
    """计算指定日期前的MA250或MA750"""
    target = pd.Timestamp(target_date)
    subset = df_bond[df_bond['date'] <= target].copy()
    if len(subset) < ma_days:
        return None
    ma = subset.tail(ma_days)['10y'].mean()
    return ma

def compute_reference_rate(months):
    """计算参考利率 = 6个月移动平均[(LPR+定存)/2]"""
    values = []
    for year, month in months:
        lpr = get_monthly_lpr(year, month)
        dep = get_monthly_deposit(year, month)
        values.append((lpr + dep) / 2)
    return np.mean(values)

def compute_base_return(ma250, ma750, spreads):
    """计算基础回报水平 = MIN(MA250+税收溢价, MA750+税收溢价)"""
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
# 3. 回溯验证：站在2025年12月31日预测各季度
# ============================================

print("\n" + "=" * 70)
print("【回溯验证】使用公开数据计算2025年各季度预定利率研究值")
print("=" * 70)

# 季度定义：计算日期 + 对应的6个月LPR/存款窗口
quarters = {
    '2024Q4': {
        'comp_date': '2024-12-31',
        'months': [(2024, 7), (2024, 8), (2024, 9), (2024, 10), (2024, 11), (2024, 12)],
        'actual': 2.34,
    },
    '2025Q1': {
        'comp_date': '2024-12-31',
        'months': [(2024, 7), (2024, 8), (2024, 9), (2024, 10), (2024, 11), (2024, 12)],
        'actual': 2.34,
    },
    '2025Q2': {
        'comp_date': '2025-03-31',
        'months': [(2024, 10), (2024, 11), (2024, 12), (2025, 1), (2025, 2), (2025, 3)],
        'actual': 2.13,
    },
    '2025Q3': {
        'comp_date': '2025-06-30',
        'months': [(2025, 1), (2025, 2), (2025, 3), (2025, 4), (2025, 5), (2025, 6)],
        'actual': 1.99,
    },
    '2025Q4': {
        'comp_date': '2025-09-30',
        'months': [(2025, 4), (2025, 5), (2025, 6), (2025, 7), (2025, 8), (2025, 9)],
        'actual': 1.90,
    },
}

results = {}

for q_name, q_info in quarters.items():
    print(f"\n{'─' * 70}")
    print(f"  季度：{q_name}")
    print(f"  计算日期：{q_info['comp_date']}")
    
    # 1. 计算参考利率
    ref_rate = compute_reference_rate(q_info['months'])
    print(f"  参考利率计算窗口：{[f'{y}-{m:02d}' for y, m in q_info['months']]}")
    print(f"  参考利率 = {ref_rate:.4f}%")
    
    # 2. 计算基础回报水平 (10年期国债移动平均 + 税收溢价)
    comp_date = q_info['comp_date']
    ma250 = compute_ma_values(comp_date, df_bond, 250)
    ma750 = compute_ma_values(comp_date, df_bond, 750)
    
    base = compute_base_return(ma250, ma750, historical_spreads)
    print(f"  10年期国债MA250 = {ma250:.4f}%")
    print(f"  10年期国债MA750 = {ma750:.4f}%")
    print(f"  税收溢价(250MA) = {base['tax_premium_250']:.4f}%")
    print(f"  税收溢价(750MA) = {base['tax_premium_750']:.4f}%")
    print(f"  250MA合计 = {base['total_250']:.4f}%")
    print(f"  750MA合计 = {base['total_750']:.4f}%")
    print(f"  基础回报水平 = MIN({base['total_250']:.4f}%, {base['total_750']:.4f}%) = {base['base_return']:.4f}%")
    
    # 3. 计算系数调节前预定利率
    pre_coeff = min(ref_rate, base['base_return'])
    print(f"  系数调节前 = MIN({ref_rate:.4f}%, {base['base_return']:.4f}%) = {pre_coeff:.4f}%")
    
    # 4. 计算最终预定利率
    final = calculate_coeff(pre_coeff)
    actual = q_info['actual']
    diff = (final - actual) * 100  # BP
    
    print(f"  ")
    print(f"  >>> 预测值 = {final:.4f}% = {final * 100:.2f}BP")
    print(f"  >>> 实际值 = {actual:.4f}% = {actual * 100:.2f}BP")
    print(f"  >>> 差异 = {diff:.1f}BP")
    
    results[q_name] = {
        'ref_rate': ref_rate,
        'ma250': ma250,
        'ma750': ma750,
        'base_return': base['base_return'],
        'pre_coeff': pre_coeff,
        'predicted': final,
        'actual': actual,
        'diff_bp': diff,
    }

# ============================================
# 4. 汇总结果
# ============================================

print("\n" + "=" * 70)
print("【汇总对比】")
print("=" * 70)
print(f"{'季度':<10} {'预测值':<10} {'实际值':<10} {'差异(BP)':<12} {'吻合度':<10}")
print("-" * 70)
for q_name in quarters.keys():
    r = results[q_name]
    diff = r['diff_bp']
    if abs(diff) < 5:
        status = '高度吻合'
    elif abs(diff) < 10:
        status = '基本吻合'
    else:
        status = '偏差较大'
    print(f"{q_name:<10} {r['predicted']:<10.4f} {r['actual']:<10.2f} {diff:<12.1f} {status:<10}")

print("\n" + "=" * 70)
print("【数据来源说明】")
print("=" * 70)
print("1. 5年期LPR：中国货币网 (www.shibor.net.cn) 历史数据")
print("2. 六大行5年定存利率：工商银行、农业银行、中国银行、建设银行、交通银行、")
print("   邮储银行官网公告 (人民网、百度新闻等公开渠道汇总)")
print("3. 10年期国债收益率：中国货币网日频数据，通过 akshare 库获取")
print("4. 国开债/进出口债利差：因日频数据无公开渠道，采用2024年底历史利差近似")
print("=" * 70)
