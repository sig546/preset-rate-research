"""
完整读取预定利率sheet，理解公式结构
"""
import pandas as pd

file_path = "C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx"
df = pd.read_excel(file_path, sheet_name='预定利率', header=None)

print("Full sheet content:")
print(f"Shape: {df.shape}")
for i in range(df.shape[0]):
    row_data = [str(df.iloc[i, j]) for j in range(df.shape[1])]
    # Filter out 'nan' values for readability
    non_nan = [(j, str(df.iloc[i, j])) for j in range(df.shape[1]) if str(df.iloc[i, j]) != 'nan']
    print(f"Row {i}: {non_nan}")

print("\n" + "="*60)
print("Read full coefficient adjustment section...")

# Read the 参考利率 part more carefully
print("\n参考利率 adjustment rows:")
for i in range(8, 18):
    row_data = [str(df.iloc[i, j]) for j in range(1, 8)]
    print(f"Row {i}: {row_data}")

# Also read 5年期LPR sheet
print("\n" + "="*60)
print("LPR Sheet:")
lpr_df = pd.read_excel(file_path, sheet_name='5年期LPR', header=None)
for i in range(min(25, len(lpr_df))):
    non_nan = [(j, str(lpr_df.iloc[i, j])) for j in range(lpr_df.shape[1]) if str(lpr_df.iloc[i, j]) != 'nan']
    print(f"Row {i}: {non_nan}")

print("\n" + "="*60)
print("Deposit Rate Sheet:")
dep_df = pd.read_excel(file_path, sheet_name='5年期定期存款利率', header=None)
for i in range(min(65, len(dep_df))):
    non_nan = [(j, str(dep_df.iloc[i, j])) for j in range(dep_df.shape[1]) if str(dep_df.iloc[i, j]) != 'nan']
    if non_nan:
        print(f"Row {i}: {non_nan}")
