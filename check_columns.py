import pandas as pd

file_path = 'C:/Users/marsh/Downloads/预定利率研究值-使用版.xlsx'

# 读取国债数据看看列名
df_gov = pd.read_excel(file_path, sheet_name='国债-到期')
print("国债数据列名:")
print(df_gov.columns.tolist())
print("\n前5行:")
print(df_gov.head())
print("\n数据形状:", df_gov.shape)
