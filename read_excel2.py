import pandas as pd

file_path = 'C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx'
xl = pd.ExcelFile(file_path)

# 详细读取"预定利率"sheet
df_rate = pd.read_excel(file_path, sheet_name='预定利率', header=None)
print("=== 预定利率Sheet完整内容 ===")
print(df_rate.to_string())
print()

# 读取input数据
df_input = pd.read_excel(file_path, sheet_name='input>', header=None)
print("\n=== Input Sheet ===")
print(df_input.to_string())
