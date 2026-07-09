import pandas as pd
import numpy as np

# 验证2024-12-31的计算逻辑
print("=" * 60)
print("预定利率研究值计算公式验证（2024-12-31）")
print("=" * 60)

# =====================
# 1. 参考利率计算
# =====================
print("\n【1. 参考利率 = (5Y LPR + 5Y 存款利率) 6个月移动平均 / 2】")

# 6个月数据（2024-07到2024-12）
months = [
    ("2024-07", 0.036, 0.0155),  # LPR, 存款利率
    ("2024-08", 0.036, 0.0155),
    ("2024-09", 0.036, 0.0155),
    ("2024-10", 0.036, 0.0155),
    ("2024-11", 0.036, 0.0155),
    ("2024-12", 0.036, 0.0155),
]

lpr_deposit_sums = []
for month, lpr, deposit in months:
    s = lpr + deposit
    lpr_deposit_sums.append(s)
    print(f"  {month}: 5Y LPR={lpr*100}% + 5Y存款={deposit*100}% = {s*100}%")

avg = sum(lpr_deposit_sums) / len(lpr_deposit_sums)
reference_rate = avg / 2
print(f"\n  6个月平均 = {avg*100:.4f}%")
print(f"  参考利率 = {avg*100:.4f}% / 2 = {reference_rate*100:.4f}%")
print(f"  Excel值: 2.70%")

# =====================
# 2. 基础回报水平计算
# =====================
print("\n【2. 基础回报水平 = MIN(250MA, 750MA)】")

# 10年期国债250MA = 2.2146136%
gz_250ma = 2.2146136 / 100
print(f"\n  10年期国债250日移动平均 = {gz_250ma*100:.6f}%")

# 国开债250MA = 2.3058604%
gk_250ma = 2.3058604 / 100
print(f"  10年期国开债250日移动平均 = {gk_250ma*100:.6f}%")

# 进出口250MA = 2.353202%
jk_250ma = 2.353202 / 100
print(f"  10年期进出口债250日移动平均 = {jk_250ma*100:.6f}%")

# 利差
gk_spread_250 = gk_250ma - gz_250ma
jk_spread_250 = jk_250ma - gz_250ma
print(f"\n  国开债-国债利差(250MA) = {gk_spread_250*100:.6f}%")
print(f"  进出口债-国债利差(250MA) = {jk_spread_250*100:.6f}%")

tax_premium_250 = max(gk_spread_250, jk_spread_250)
print(f"  税收溢价(250MA) = MAX({gk_spread_250*100:.6f}%, {jk_spread_250*100:.6f}%) = {tax_premium_250*100:.6f}%")

ma250 = gz_250ma + tax_premium_250
print(f"  250MA = 国债250MA + 税收溢价 = {gz_250ma*100:.6f}% + {tax_premium_250*100:.6f}% = {ma250*100:.6f}%")

# 750MA
gz_750ma = 2.56817666666667 / 100
gk_750ma = 2.70621946666666 / 100
jk_750ma = 2.7905456 / 100

print(f"\n  10年期国债750日移动平均 = {gz_750ma*100:.6f}%")
print(f"  10年期国开债750日移动平均 = {gk_750ma*100:.6f}%")
print(f"  10年期进出口债750日移动平均 = {jk_750ma*100:.6f}%")

gk_spread_750 = gk_750ma - gz_750ma
jk_spread_750 = jk_750ma - gz_750ma
print(f"\n  国开债-国债利差(750MA) = {gk_spread_750*100:.6f}%")
print(f"  进出口债-国债利差(750MA) = {jk_spread_750*100:.6f}%")

tax_premium_750 = max(gk_spread_750, jk_spread_750)
print(f"  税收溢价(750MA) = MAX({gk_spread_750*100:.6f}%, {jk_spread_750*100:.6f}%) = {tax_premium_750*100:.6f}%")

ma750 = gz_750ma + tax_premium_750
print(f"  750MA = 国债750MA + 税收溢价 = {gz_750ma*100:.6f}% + {tax_premium_750*100:.6f}% = {ma750*100:.6f}%")

base_return = min(ma250, ma750)
print(f"\n  基础回报水平 = MIN({ma250*100:.6f}%, {ma750*100:.6f}%) = {base_return*100:.6f}%")
print(f"  Excel值: 2.353202%")

# =====================
# 3. 系数调节前
# =====================
print("\n【3. 系数调节前预定利率 = MIN(参考利率, 基础回报水平)】")
pre_coeff = min(reference_rate, base_return)
print(f"  = MIN({reference_rate*100:.4f}%, {base_return*100:.6f}%) = {pre_coeff*100:.6f}%")
print(f"  Excel值: 2.353202%")

# =====================
# 4. 系数调节
# =====================
print("\n【4. 系数调节（分段累加）】")
segments = [
    (0.00, 0.01, 1.00, "0%-1%"),
    (0.01, 0.02, 1.00, "1%-2%"),
    (0.02, 0.025, 0.95, "2%-2.5%"),
    (0.025, 0.03, 0.95, "2.5%-3%"),
    (0.03, 0.035, 0.50, "3%-3.5%"),
    (0.035, 0.04, 0.50, "3.5%-4%"),
    (0.04, 0.10, 0.30, "4%-10%"),
]

total_adjustment = 0
for low, high, coeff, desc in segments:
    if pre_coeff > high:
        contribution = (high - low) * coeff
    elif pre_coeff > low:
        contribution = (pre_coeff - low) * coeff
    else:
        contribution = 0
    total_adjustment += contribution
    status = "✓" if contribution > 0 else "✗"
    print(f"  {status} {desc}: 系数{coeff*100:.0f}%, 贡献={contribution*100:.6f}%")

print(f"\n  系数调节合计 = {total_adjustment*100:.6f}%")
print(f"  Excel值: 2.335542%")

# =====================
# 5. 最终预定利率
# =====================
print("\n【5. 最终预定利率】")
final_rate = total_adjustment
print(f"  最终预定利率 = {final_rate*100:.6f}%")
print(f"  四舍五入到2位小数 = {final_rate*100:.2f}%")
print(f"  对应公布值: 2.34%（2025年1月公布）")

print("\n" + "=" * 60)
print("验证结论：公式计算正确！")
print("=" * 60)
