# 预定利率研究值 - 历史数据·预测·触发分析

本项目展示中国保险行业协会公布的"预定利率研究值"历史数据、模型预测值及监管调整触发分析。

## 页面结构

| 页面 | 文件 | 内容 |
|------|------|------|
| 主页 | `index.html` | 指标卡片、趋势图、数据表、触发监测、预测详情、计算公式、监管规则 |
| 机构观点 | `prediction_views.html` | 6家机构完整观点汇总 |
| 计算公式 | `formula_report.html` | 五步计算逻辑、数据源详解、回溯验证 |
| 触发分析 | `trigger_analysis_report.html` | 差值分析、趋势图、事件时间线、敏感性分析 |

## 部署到 GitHub Pages

### 第一步：注册 GitHub 账户

1. 访问 https://github.com/signup
2. 填写用户名、邮箱、密码完成注册
3. 验证邮箱

### 第二步：创建 Personal Access Token

1. 登录 GitHub，访问 Settings > Developer settings > Personal access tokens > Tokens (classic)
2. 点击 "Generate new token (classic)"
3. Note 填写 "deployment"
4. Expiration 选择 "No expiration"（或按需选择）
5. 勾选 `repo` 权限（包含 repo:status, repo_deployment, public_repo, write:packages 等）
6. 点击 "Generate token"
7. **复制 token 并妥善保存**（页面关闭后无法再查看）

### 第三步：一键部署（推荐）

完成前两步后，在项目目录下运行：

```bash
python deploy_to_github.py
```

脚本会自动完成：创建仓库 → 推送代码 → 启用 GitHub Pages，全程无需手动操作。

### 手动部署（替代方案）

如需手动操作，按以下步骤进行：

1. 访问 https://github.com/new 创建仓库
2. Repository name 填写 `preset-rate-research`
3. 选择 **Public**（GitHub Pages 免费版需要 Public 仓库）
4. **不要**勾选 "Add a README file"、"Add .gitignore"、"Choose a license"
5. 点击 "Create repository"

### 第四步：推送代码

在本项目目录下打开终端（Git Bash 或 PowerShell），执行：

```bash
# 配置 Git 用户信息（替换为你的 GitHub 用户名和邮箱）
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的邮箱"

# 初始化仓库并提交
cd "项目路径"
git init
git add .
git commit -m "Initial commit: 预定利率研究值网站"

# 关联远程仓库并推送（替换 用户名 和 仓库名）
git remote add origin https://github.com/用户名/preset-rate-research.git
git branch -M main
git push -u origin main
```

推送时会弹出认证窗口，输入 GitHub 用户名和刚才创建的 Token。

### 第五步：启用 GitHub Pages

1. 进入仓库的 Settings > Pages
2. Source 选择 **GitHub Actions**
3. 保存后，推送代码时会自动触发部署

### 第六步：访问网站

部署完成后（约1-2分钟），在仓库的 Settings > Pages 页面会显示网址：

```
https://用户名.github.io/preset-rate-research/
```

## 更新网站内容

修改本地文件后，执行以下命令即可自动重新部署：

```bash
git add .
git commit -m "Update: 描述修改内容"
git push
```

GitHub Actions 会自动重新构建并发布。

## 技术说明

- 纯静态网站（HTML + CSS + JavaScript）
- 使用 Chart.js 绘制图表（通过 CDN 加载）
- 无后端依赖，无需服务器
- GitHub Pages 免费托管，支持 HTTPS

## 数据来源

- 中国保险行业协会（研究值公布）
- 中国货币网（LPR、国债收益率）
- 六大国有银行官网（定存利率）
- AkShare（国债收益率历史数据）
- 平安人寿官网（预定利率最高值公告）

## 债券收益率数据源策略（cdb_10y / ieb_10y）

国开债 10Y（`cdb_10y`）与进出口行债 10Y（`ieb_10y`）用于计算税收溢价（`spread`），采用**混合数据源**策略：

| 时间段 | 数据源 | 说明 |
|--------|--------|------|
| 2002-01-04 ~ 2026-03-31（长历史，6055 天） | **中债估值** | 一次性由 Excel（`data_国开债和进出口银行债 for workbuddy.xlsx`）导入补齐 |
| 2026-04-01 ~ 2026-07-08（近 67 天） | **中国货币网** | `scripts/fill_cdb_ieb.py` 直连货币网 `ClsYldCurvHis` 接口抓取的真实值 |
| 2026-07-09 起（后续） | **中国货币网** | 由 GitHub Actions 按月增量抓取货币网数据累积 |

**说明与依据：**

- 两套口径（货币网 vs 中债估值）在重叠的近 67 天内逐日差异均在 **1 BP 以内**（国开债 ≤0.45 BP、进出口债 ≤0.84 BP），属正常估值差异，无异常错值。
- 经只读对比验证（`scripts/compare_sources.py`）：由于税收溢价使用 250/750 交易日移动平均，近期口径差异传导到最终研究值后 **≤0.03 BP**，四舍五入后两套预测结果完全一致（均为 1.93%，不触发下调）。因此近期保留货币网、长历史用中债的混合口径，对预测无实质影响。
- 单位统一为 **%**（如 `1.7855` 表示 1.7855%），保留 4 位小数。
- 合并脚本：`scripts/merge_excel_cdb_ieb.py`（近 67 天保留货币网、其余用 Excel 补齐）；原始文件备份为 `data/bond_yields.backup_20260709.json`。

> ⚠️ 中国货币网 `ClsYldCurvHis` 接口仅保留约最近 3 个月历史（2026-04-01 起），更早日期返回空，故长历史只能由 Excel 一次性导入，无法从接口回补。
