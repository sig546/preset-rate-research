import pandas as pd

# 读取Excel文件的所有sheet
file_path = 'C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx'

# 获取所有sheet名称
xl = pd.ExcelFile(file_path)
print("=== Sheet名称 ===")
print(xl.sheet_names)
print()

# 读取每个sheet的内容
for sheet_name in xl.sheet_names:
    print(f"\n{'='*60}")
    print(f"Sheet: {sheet_name}")
    print(f"{'='*60}")
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    print(df.to_string())
    print()
