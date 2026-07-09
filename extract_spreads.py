"""
从Excel中提取2024年底的国开债、进出口债利差数据
作为公开数据的近似值
"""
import pandas as pd

file_path = "C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx"
df = pd.read_excel(file_path)

# 打印所有sheet名
xl = pd.ExcelFile(file_path)
print("Sheets:", xl.sheet_names)

for sheet in xl.sheet_names:
    df = pd.read_excel(file_path, sheet_name=sheet, header=None)
    print(f"\n{'='*60}")
    print(f"Sheet: {sheet}")
    print(f"Shape: {df.shape}")
    # Find cells containing 国开 or 进出口 or 利差
    for col in range(df.shape[1]):
        for row in range(df.shape[0]):
            val = str(df.iloc[row, col])
            if any(kw in val for kw in ['国开', '进出口', '利差', 'spread']):
                print(f"  [{row},{col}] {val}")
                # Print surrounding context
                for r in range(max(0,row-1), min(df.shape[0], row+3)):
                    row_vals = [str(df.iloc[r, c]) for c in range(min(df.shape[1], col+5))]
                    print(f"    Row {r}: {row_vals}")

# 也检查全部内容
print(f"\n{'='*60}")
print("检查所有sheet的前几行:")
for sheet in xl.sheet_names:
    df = pd.read_excel(file_path, sheet_name=sheet, header=None)
    print(f"\n--- {sheet} ---")
    for i in range(min(5, len(df))):
        print(f"Row {i}: {[str(df.iloc[i, j]) for j in range(min(10, df.shape[1]))]}")
