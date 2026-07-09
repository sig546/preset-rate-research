# 项目迁移指南

## 文件清单

压缩包 `preset_rate_research_YYYYMMDD.zip` 包含以下内容：

```
preset_rate_research/
├── index.html                        # 主页（核心页面）
├── prediction_views.html             # 机构观点子页
├── formula_report.html               # 计算公式报告
├── trigger_analysis_report.html      # 触发分析报告
├── prediction_report.html            # 预测报告
├── prediction_report_corrected.html  # 预测报告（修正版）
├── formula_analysis.html             # 公式分析
├── formula_analysis_v2.html          # 公式分析v2
│
├── data/                             # 数据文件
│   ├── actuals.json                  # 实际公布值
│   ├── predictions.json              # 预测值
│   ├── bond_yields.json              # 债券日频收益率
│   ├── lpr_history.json              # 5Y LPR历史
│   ├── deposit_rates.json            # 5Y定存利率历史
│   └── pingan_announcements.json     # 平安人寿公告
│
├── scripts/                          # 自动化脚本
│   ├── update_actuals.py             # 实际值自动更新
│   ├── update_predictions.py         # 预测值自动更新
│   ├── check_pingan.py               # 平安人寿公告检核
│   └── generate_excel.py             # 生成Excel汇总
│
├── .github/workflows/                # GitHub Actions
│   ├── update-actuals.yml            # 实际值定时更新
│   ├── update-predictions.yml        # 预测值定时更新
│   └── deploy.yml                    # GitHub Pages部署
│
├── requirements.txt                  # Python依赖清单
├── .gitignore                        # Git忽略规则
├── README.md                         # 项目说明
├── deploy_to_github.py               # GitHub Pages部署脚本
├── package.py                        # 打包脚本（本文件）
│
└── *.py                              # 各类分析/回溯脚本
```

## 目标电脑恢复步骤

### 前置条件

- Python 3.10+（推荐 3.12+）
- Git（可选，用于版本管理和推送到GitHub）
- 操作系统：Windows / macOS / Linux 均可

### 步骤 1：解压

```bash
unzip preset_rate_research_YYYYMMDD.zip
cd preset_rate_research
```

### 步骤 2：安装 Python 依赖

```bash
pip install -r requirements.txt
```

> 建议使用虚拟环境：
> ```bash
> python -m venv venv
> source venv/bin/activate    # macOS/Linux
> venv\Scripts\activate       # Windows
> pip install -r requirements.txt
> ```

### 步骤 3：浏览主页（无需任何配置）

直接用浏览器打开 `index.html` 即可查看完整的主页和数据。

> 注：数据加载需要本地文件服务。双击打开可能因跨域限制无法加载 JSON 数据。建议使用本地服务器：
> ```bash
> # Python 3
> python -m http.server 8000
> # 然后访问 http://localhost:8000
> ```

### 步骤 4：运行自动更新（可选）

```bash
# 更新实际值（搜索中保协官网最新公布）
python scripts/update_actuals.py

# 更新预测值（基于最新债券数据）
python scripts/update_predictions.py

# 生成Excel汇总
python scripts/generate_excel.py
```

### 步骤 5：部署到 GitHub Pages（可选）

参见 `README.md` 中的部署说明。

## 环境变量与配置文件

### 无需配置的文件

以下文件开箱即用，无需修改：

| 文件 | 说明 |
|------|------|
| `data/actuals.json` | 已包含最新实际值 |
| `data/predictions.json` | 已包含最新预测值 |
| `data/lpr_history.json` | 已包含2023年至今LPR历史 |
| `data/deposit_rates.json` | 已包含六大行定存利率历史 |
| `data/pingan_announcements.json` | 已包含平安公告记录 |
| `data/bond_yields.json` | 初始为空，首次运行 update_predictions.py 时自动填充 |

### 运行脚本需要的网络访问

| 脚本 | 需要的网络访问 | 用途 |
|------|-------------|------|
| `update_actuals.py` | DuckDuckGo, 新华网 | 搜索最新研究值 |
| `update_predictions.py` | 东方财富, 中国货币网 | 获取债券/LPR数据 |
| `check_pingan.py` | DuckDuckGo, 新华网 | 搜索平安公告 |
| `generate_excel.py` | 无 | 纯本地生成 |

### 注意事项

1. **首次运行 `update_predictions.py`**：需要批量拉取约3年的债券历史数据（国开债/进出口债按月分批获取），首次运行约需3-5分钟。

2. **`index.html` 本地浏览**：直接用浏览器 `file://` 协议打开时，JSON 数据加载可能失败。推荐使用 `python -m http.server` 启动本地服务器后访问。

3. **跨平台兼容**：所有脚本使用 Path 和 os.path，兼容 Windows/macOS/Linux。

4. **Excel 文件**：运行 `python scripts/generate_excel.py` 可随时重新生成 `预定利率研究值_数据汇总.xlsx`。
