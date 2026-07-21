# 一致性检核执行记录（2026-07-10）

> 自动生成自 `scripts/run_checklist.py`，对应 `docs/一致性检核清单.md`。

## 基本信息

- 仓库：`sig546/preset-rate-research`
- 检核 commit：`554ba7b`
- 运行时间：2026-07-10 17:13:47
- 运行环境：local/managed python 3.13
- 预测值快照：2026Q2=1.9313 / 2026Q3=1.9094 / 2026Q4=1.8606 / 2027Q1=1.8135
- 实际值快照：2024Q4=2.34 / 2025Q1=2.13 / 2025Q2=1.99 / 2025Q3=1.9 / 2025Q4=1.89 / 2026Q1=1.93

## 执行记录（基于清单模板）

| 检查项 | 结果 | 备注 / 修订 commit |
|--------|------|-------------------|
| C1 预测值 SSOT | ✅ | 两页均引用 predictions.json，无分叉硬编码；当前四值 [1.9313, 1.9094, 1.8606, 1.8135] |
| C2 实际值三处一致 | ✅ | actuals.json 六季（2024Q4..2026Q1）index.html 经 actuals.json 加载；formula_report.html 均含对应值 |
| C3 最高值口径 | ✅ | actuals.json 最高值：≤2025Q2 为 2.50%、≥2025Q3 为 2.00%；页面无 2026 季度误标 2.50% |
| C4 数据源声明 | ✅ | bond_yields.json=6122 条，2002-01-04~2026-07-08，与 formula_report.html 声明一致 |
| C5 引用有效 | ✅ | 无旧脚本/死链引用；核心页面 LPR 来源 chinamoney.com.cn；公式说明指向 scripts/update_predictions.py |
| C6 更新时间 | ✅ | trigger_analysis_report.html 页脚 dataUpdated 绑定 predictions.json.last_updated；index.html 显示最新数据季度 |
| C7 预测可复算 | 🔍 | 离线复算四步公式 == predictions.json（误差≤0.0001）已于 commit f94bddc 重生时验证；CI 默认不重跑网络抓取，建议数据更新后人工执行 scripts/update_predictions.py 复算核对 |
| C8 分段累加 | ✅ | 脚本 apply_segment 为逐段累加，2.5~3.0 段系数 0.95，与公式页系数表一致（回溯模型B avg|差|=1.42BP） |
| C9 平推假设 | ✅ | 四季差值 [6.9, 9.1, 13.9, 18.7] BP 均<25，平推（未来 LPR=3.50%/定存=1.30%/债券=1.7385% 维持不变）自洽 |
| C10 回溯汇总/明细 | ✅ | backtest_history.json（avg=1.42, max=2.69, min=0.42）与公式页声明一致 |
| C11 触发主表/明细 | ✅ | 主表与预测明细表均由 predictions.json 同一数组渲染，构造上一致 |
| P1 核心术语唯一 | ⚠️ | 核心页面通过；遗留页面 ['prediction_report.html', 'prediction_report_corrected.html'] 仍用「信用债利差」等旧术语（技术债） |
| P2 分段系数表 | ✅ | 脚本 SEGMENT_COEFF 与 formula_report 系数表逐段一致（2.5~3.0=0.95 等） |
| P3 基础回报公式 | ✅ | index 与 formula_report 均使用紧凑式（= MA(gov)+MA(税收溢价)），与脚本一致 |
| P4 触发阈值 | ⚠️ | 核心页面通过；遗留页面 ['prediction_report.html'] 含异版阈值（20BP/连续3季度，技术债） |
| P5 预测趋势逻辑 | ✅ | 未见「预测利率将下行」类表述；图表下行与「MA 窗口效应」叙述自洽 |
| P6 时间线 | ✅ | actuals 止于 2026Q1，predictions 起于 2026Q2，无错位 |
| P7 章节标题 | ✅ | 公式页章节标题均贴合内容（第二步=税收溢价，无标题/内容错配） |
| P8 图表=表格=源 | ✅ | 两张 Chart 由 predRes.predictions / actRes.actuals 同源渲染，图=表=源一致 |
| P9 图表标注 | ✅ | gapChart 含 25BP 触发线标注（TRIGGER_THRESHOLD=0.25）；trendChart 含最高值阶梯线 |
| F1 百分比统一 | ✅ | 研究值主表 2 位 / 明细 4 位分区明确，未见混用 3 位小数 |
| F2 BP 单位 | ⚠️ | 核心页面统一「BP」；遗留页面 ['prediction_report.html', 'prediction_report_corrected.html', 'formula_analysis.html', 'formula_analysis_v2.html'] 仍混用「个基点」/小写 bp（技术债） |
| F3 小数位数 | ⚠️ | predictions.json 同类字段小数位不统一（如 ma250_gov 出现 [2, 3, 4] 位混用），建议生成时补零至 4 位以保证展示一致 |
| F4 标点/连接号 | 🔍 | 中文全角标点、季度区间连接号（~ / ～）、日期 YYYY-MM-DD 风格需人工目视核对全站一致性 |
| F5 季度编号 | ✅ | 2024Q4→2027Q1 连续无重复遗漏，实际/预测分界清晰 |
| F6 章节/图编号 | ✅ | 公式页第一~第五步编号连续无跳号/重复 |
| F7 字段命名 | ✅ | 页面读取字段名与 predictions.json/actuals.json 字段名一致，无拼写漂移 |
| A1 一致性校验 | ✅ | check_data_consistency.py 规则1-4 通过（EXIT=0） |
| A2 数据不过期 | ✅ | last_updated=2026-07-10 13:51（0.1 天前，≤40） |
| A3 发版后实测 | 🔍 | 发版后由独立步骤/手动执行：curl 抓取线上两页，确认无旧值 1.9383、均引用 predictions.json、last_updated 一致。本次试运行已附带 LIVE_CHECK=1 实测。 |

| **整体结论** | **⚠️ 通过（4 项提示，需关注）** | FAIL=0, WARN=4 |

## 详细备注

- **C1 预测值 SSOT** ✅ — 两页均引用 predictions.json，无分叉硬编码；当前四值 [1.9313, 1.9094, 1.8606, 1.8135]
- **C2 实际值三处一致** ✅ — actuals.json 六季（2024Q4..2026Q1）index.html 经 actuals.json 加载；formula_report.html 均含对应值
- **C3 最高值口径** ✅ — actuals.json 最高值：≤2025Q2 为 2.50%、≥2025Q3 为 2.00%；页面无 2026 季度误标 2.50%
- **C4 数据源声明** ✅ — bond_yields.json=6122 条，2002-01-04~2026-07-08，与 formula_report.html 声明一致
- **C5 引用有效** ✅ — 无旧脚本/死链引用；核心页面 LPR 来源 chinamoney.com.cn；公式说明指向 scripts/update_predictions.py
- **C6 更新时间** ✅ — trigger_analysis_report.html 页脚 dataUpdated 绑定 predictions.json.last_updated；index.html 显示最新数据季度
- **C7 预测可复算** 🔍 — 离线复算四步公式 == predictions.json（误差≤0.0001）已于 commit f94bddc 重生时验证；CI 默认不重跑网络抓取，建议数据更新后人工执行 scripts/update_predictions.py 复算核对
- **C8 分段累加** ✅ — 脚本 apply_segment 为逐段累加，2.5~3.0 段系数 0.95，与公式页系数表一致（回溯模型B avg|差|=1.42BP）
- **C9 平推假设** ✅ — 四季差值 [6.9, 9.1, 13.9, 18.7] BP 均<25，平推（未来 LPR=3.50%/定存=1.30%/债券=1.7385% 维持不变）自洽
- **C10 回溯汇总/明细** ✅ — backtest_history.json（avg=1.42, max=2.69, min=0.42）与公式页声明一致
- **C11 触发主表/明细** ✅ — 主表与预测明细表均由 predictions.json 同一数组渲染，构造上一致
- **P1 核心术语唯一** ⚠️ — 核心页面通过；遗留页面 ['prediction_report.html', 'prediction_report_corrected.html'] 仍用「信用债利差」等旧术语（技术债）
- **P2 分段系数表** ✅ — 脚本 SEGMENT_COEFF 与 formula_report 系数表逐段一致（2.5~3.0=0.95 等）
- **P3 基础回报公式** ✅ — index 与 formula_report 均使用紧凑式（= MA(gov)+MA(税收溢价)），与脚本一致
- **P4 触发阈值** ⚠️ — 核心页面通过；遗留页面 ['prediction_report.html'] 含异版阈值（20BP/连续3季度，技术债）
- **P5 预测趋势逻辑** ✅ — 未见「预测利率将下行」类表述；图表下行与「MA 窗口效应」叙述自洽
- **P6 时间线** ✅ — actuals 止于 2026Q1，predictions 起于 2026Q2，无错位
- **P7 章节标题** ✅ — 公式页章节标题均贴合内容（第二步=税收溢价，无标题/内容错配）
- **P8 图表=表格=源** ✅ — 两张 Chart 由 predRes.predictions / actRes.actuals 同源渲染，图=表=源一致
- **P9 图表标注** ✅ — gapChart 含 25BP 触发线标注（TRIGGER_THRESHOLD=0.25）；trendChart 含最高值阶梯线
- **F1 百分比统一** ✅ — 研究值主表 2 位 / 明细 4 位分区明确，未见混用 3 位小数
- **F2 BP 单位** ⚠️ — 核心页面统一「BP」；遗留页面 ['prediction_report.html', 'prediction_report_corrected.html', 'formula_analysis.html', 'formula_analysis_v2.html'] 仍混用「个基点」/小写 bp（技术债）
- **F3 小数位数** ⚠️ — predictions.json 同类字段小数位不统一（如 ma250_gov 出现 [2, 3, 4] 位混用），建议生成时补零至 4 位以保证展示一致
- **F4 标点/连接号** 🔍 — 中文全角标点、季度区间连接号（~ / ～）、日期 YYYY-MM-DD 风格需人工目视核对全站一致性
- **F5 季度编号** ✅ — 2024Q4→2027Q1 连续无重复遗漏，实际/预测分界清晰
- **F6 章节/图编号** ✅ — 公式页第一~第五步编号连续无跳号/重复
- **F7 字段命名** ✅ — 页面读取字段名与 predictions.json/actuals.json 字段名一致，无拼写漂移
- **F8 离线快照时效** ✅ — index.html 离线快照 SNAPSHOT_UPDATED=2026-07-10 13:51 与 predictions.json.last_updated 一致
- **A1 一致性校验** ✅ — check_data_consistency.py 规则1-4 通过（EXIT=0）
- **A2 数据不过期** ✅ — last_updated=2026-07-10 13:51（0.1 天前，≤40）
- **A3 发版后实测** 🔍 — 发版后由独立步骤/手动执行：curl 抓取线上两页，确认无旧值 1.9383、均引用 predictions.json、last_updated 一致。本次试运行已附带 LIVE_CHECK=1 实测。
