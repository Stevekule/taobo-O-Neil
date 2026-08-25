


# 真实RPS 账户回测流水线

把 `taobo-O'Neil` skill 的**RPS 取数**接入回测基建，产出符合实际账户口径（100万本金 / 万5手续费 / 次日开盘成交 / -8%止损）的回测结果。

## 回测区间与规则（2026-08-10 用户指令 · 已更新）

> **回测区间：2011-2026（16年）**（2026-08-14 扩区间：原 2016-2025 扩展；历史扩展依赖自算全市场 RPS 2010 起）。七条规则不变：
> 1. **真实账户收益逐笔统计**：初始 100 万，按账户净值逐日计算，单笔交易亏损即账户实际损失（-8%止损×仓位≈账户-1.6%~-2%含手续费），手续费万5单边最低5元计入。
> 2. **RPS 统计口径 = 全市场分位**（非池内分位）：RPS250/120/50/20/10 = 个股在**全市场**当日涨幅排名分位。⚠️ **2026-08-14 重大修正**：旧版 `rps_market_2016_2025.csv` 实为**池内分位**（每日仅 ~497 只，违反规则），**旧信号与旧回测结论（dr 最优 +909%/+1266%）全部作废**；新版自算 `rps_market_2010_2026.csv`（全市场分位，每日 ~5000 只）为唯一口径。**方案B（2026-08-11 拍板，2026-08-14 新口径复核确认）**：信号生成 + R7-1 淘弱判定 = 全市场分位；**R7-2 腾位排序 = 池内分位**（持仓间相对强弱；新口径验证段 adaptive pool +1066% vs market +947%，dr 亦 pool 优 → 维持池内）。
> 3. **数据本地优先**：K线/指数/RPS 先读本地（`vipdoc/*/lday/*.day`、`kline_v2_2010/`、`kline_index_2010/`、`rps_market_2010_2026.csv`）；本地缺失/异常 → 走通达信 MCP（`tdx_kline`）补齐。**北交所（920xxx）不交易，已从池剔除**。
> 4. **建仓金额 = 动态净值×10% + 无 slot（唯一规则，2026-08-10 定稿 · 直接作为回测规则，非对照项）**：`--pos-size-mode nav` 且**不加任何单票占比约束**（slot/fixed20 均不启用）。固定金额已废弃删除；slot 已证伪（60 组合开优1/关优19/持平10）。依据：动态净值 21/24 子组合最优（牛市复利加速+熊市反脆弱）；slot 高收益组合杀伤 -470pp。**占比规则不再纳入交叉验证维度**。
> 5. **所有回测必须做完整交叉验证（2026-08-10 定稿）**：任何策略结论必须先跑**全维度组合网格**，禁止单一骨架下结论。**必跑维度（占比规则固定为动态净值×10%+无slot，不再交叉）**：**离场引擎（dr/peak/adaptive/albrooks/oneil/hybrid）× 持仓上限（P555/P864/P1284）× 门控（G0无/G1/G2/G3/GA自适应）× R7-2（R0关/R72开）** = 180 组合。网格脚本 `run_exit_grid_v3.py`（4进程并行）+ `collect_v3_summary.py` + `gen_v3_report.py`（180 组合报告 + 分段报告）。
> 6. **回测输出必须含强制指标（2026-08-10 定稿 · 2026-08-14 补算扩展 · 2026-08-16 口径钉死）**：每次回测报告必须含——**① 总收益（全区间累计）② 赔率（全区间 + 每年）③ 胜率（全区间 + 每年）④ 年收益（分年明细）⑤ 平均胜率（跨 180 组合 win_rate 简单均值 + 笔数加权均值）⑥ 平均年化收益 CAGR（每组合 (1+总收益/100)^(1/N)-1 的跨组合均值，TOP1 年化单列）**。**报告必须含「每年 + 全区间」的 胜率/赔率/平均收益/总收益率 明细表**（禁用仅列年收益；须覆盖**全部 6 引擎 × 3 持仓骨架（5-5-5 / 8-6-4 / 12-8-4）· 同门控 G2·R7-2 的逐年明细**（含逐年横向透视），旧 v4 仅列年收益已补正为 v4.1 章节⑥）；引擎 `--stats-out <json>` 落盘（`{year:{...}, ALL:{...}, env:{...}}`，**env=环境分段 2026-08-14 新增**），网格批量跑自动保存 `bt_*/w*.json`；报告由 `gen_v4_report_ext.py` 生成 `v4.1-grid-report-YYYYMMDD.html`（含 KPI 平均胜率/年化 + 章节⑥ 全部 6 引擎×3骨架逐年全维度 + 章节⑦ 跨组合聚合），脚本与数据同在 `deliverables/taobo-daily/`。
>
> **📐 可机械执行口径（2026-08-16 钉死，禁止自由发挥）**：
> - **年化折算年限 N** = 回测区间末年份 − 首年份 + 1（含首尾）；当前 2011-2026 → **N=16**。换区间须按同式重算，**禁止硬编码 16**。例：2016-2025 → N=10。
> - **平均年化收益 CAGR** = (1 + 总收益_pct/100)^(1/N) − 1（几何年化，用于跨策略可比）。**终值保护**：总收益 ≤ −100%（账户归零/终值≤0）的组合折算无意义，计算「跨组合均值」时**跳过**，并在口径说明标注跳过个数。跨组合均值 = 各组合 CAGR 算术平均；**TOP1 年化** = 对全区间总收益最高组合单独算 CAGR 单列。
> - **平均胜率**（两项并列输出、不互相替代）：**简单均值** = Σ(各组合 win_rate) / 组合数（=180，网格横向均值）；**笔数加权** = Σ(win_rate_i × n_i) / Σn_i（等同合并 180 组合所有笔数的合并胜率）。
> 7. **回测区间结束仍未清仓的标的单独观察至清仓为止（2026-08-11 用户指令定稿）**：**到期规则不变**——dr 引擎 120 日 / 其余引擎 250 日到期**仍强制平仓**。**仅对回测区间结束（end_date）仍未平仓的持仓**，**单独延展观察至真实清仓信号**。实现：引擎 `--extend-open`；延展结果单独输出 `[extend]` 区块，**不计入主区间净值与赔率/胜率统计**。

## 关键事实（不可改）
- **本地RPS取数由 `taobo-O'Neil` skill 拥有（单一真源）**：个股/板块 RPS 由该 skill 的 `references/rps_lookup.py` 读通达信 EXTDATA 提供（C4-C6/双RPS）。本流水线 `gen_signals_realrps_2016_2025.py` 已通过 `sys.path.insert(0, r"<TAOBO_SKILL_REFS>/references")` 直接 `import rps_lookup` 复用，**不另立副本**。完整契约（数据结构/ID映射/`get_stock_rps_series`/`asof`无前视/双RPS自动映射/刷新时效）见 `taobo-O'Neil` SKILL.md Step 3 第2层 与 `rps_lookup.py` 模块 docstring——本 skill 只消费、不改写。
- **全市场分位 RPS（回测唯一口径，2026-08-14 定稿）**：**自算版** `tdx_data/rps_market_2010_2026.csv`（**1166 万行/每日 ~5000 只全市场**、2011 起完整 5 档 rps250/120/50/20/10、0-100 分位；`build_market_close_2010.py` 快照重建 → `filter_a_share.py` A股白名单过滤 → `calc_rps_market_2010_v2.py` 计算）。⚠️ **旧 `rps_market_2016_2025.csv` 实为池内分位（每日 ~497 只），口径错误，仅作历史对照**。通达信 EXTDATA 解析版 `rps_market_2005_2026.csv`（2015 起完整）作交叉验证源——与自算版 2025-06 抽样 4943 只对比：相关 0.942、平均差 5.04、47% 差<3（✅ 口径一致；残差=通达信含退市股基数略大）。**板块 RPS 已确认与本地行业归属同源**（880板块指数=T代码行业，tdxzs.cfg 映射 146 个行业板块，ext11/12/13 = 板块 RPS5/10/20）。
- C4 硬门槛（陶博士锚定，不可改）：**RPS120≥90 或 RPS250≥90**。C5=一线红(任一≥90)、C6=三线红(三者≥90)。双RPS=个股C4 + 所属板块RPS20≥90（记录 verdict，不否决）。

## 数据准备（2011-2026 · 2026-08-14 已重建）

| 数据 | 路径 | 说明 |
|------|------|------|
| 池（512只，剔北交所） | `tdx_data/screener_pool_full_no_bj.csv` | 546 → 512（删 34 只 920xxx 北交所：不交易） |
| 池内K线（2010起） | `tdx_data/kline_v2_2010/` | 512 只，从本地 .day 全历史重建（0 缺失） |
| 指数序列（2010起） | `tdx_data/kline_index_2010/` | 000001/399001/399106/399006，各 4034 条（399006 从 2010-06） |
| 全市场收盘快照 | `tdx_data/market_close_a.db` | SQLite 1394 万行 A 股（date 索引）；原始 `market_close_2010_2026.csv` 2061 万行含非个股已废弃 |
| **✅ 全市场分位RPS（唯一口径）** | `tdx_data/rps_market_2010_2026.csv` | **自算**：1166 万行/每日 ~5000 只/2011 起完整/5 档（rps250/120/50/20/10）/0-100 分位/日期无横线 |
| 通达信RPS（交叉验证） | `tdx_data/rps_market_2005_2026.csv` | EXTDATA 解析版，2015 起完整，与自算版相关 0.942 ✅ |
| **✅ 信号（2011-2026）** | `tdx_data/signals_2010_2026_realrps.csv` | **5226 个信号**（2011=51~2025=1505），自算全市场分位口径；2016-2025 重叠期与旧信号保留 76%（差异=口径纠错） |
| ~~旧信号（已作废）~~ | `tdx_data/signals_2016_2025_realrps.csv` | 池内分位口径（错误），仅作对照 |

## 流水线（4 步，脚本均在 `deliverables/taobo-daily/`）

### ① 重筛信号（2011-2026 · 全市场分位 RPS 口径）
`python gen_signals_realrps_2010_2026.py`（2026-08-14 已产出 signals_2010_2026_realrps.csv，5226 个）
- 复用 `backtest_v2_engine.detect_patterns / trend_state`（形态/趋势口径不变），RPS 走**全市场分位**（读 `rps_market_2010_2026.csv`，asof 信号日）。
- **性能要点（必看）**：预计算 SMA 数组后内联（行为一致）→ 512只×16年 60-80 秒跑完。
- 输出 `tdx_data/signals_2010_2026_realrps.csv`（code,name,signal_date,pattern,rps,trend,c4,c5,c6,double_rps,resonance,best_board,verdict,note）。
- 同个股 20 交易日冷却。⚠️ 日期格式：信号日期无横线（20110119），引擎 load_signals 已兼容；RPS 日期同样无横线。

### ② 个股份赔率/胜率
```
python backtest_v2_engine.py --pool tdx_data/screener_pool_full.csv --kline-dir tdx_data/kline_v2_2016 \
  --signals-in tdx_data/signals_2016_2025_realrps.csv --exit-mode trailing --out tdx_data/bt_realrps_trailing.csv
python backtest_v2_engine.py ... --exit-mode oneil --out tdx_data/bt_realrps_oneil.csv
# 带 R6 盈利保护（BE）口径，务必与无BE版一起跑，报告要做对照
python backtest_v2_engine.py ... --exit-mode trailing --be-stop --be-stop-th 0.10 --out tdx_data/bt_realrps_trailing_be.csv
python backtest_v2_engine.py ... --exit-mode oneil   --be-stop --be-stop-th 0.10 --out tdx_data/bt_realrps_oneil_be.csv
python analyze_odds.py --bt tdx_data/bt_realrps_trailing.csv --signals tdx_data/signals_2016_2025_realrps.csv \
  --out tdx_data/odds_realrps_trailing.json --label "移动止盈"
python analyze_odds.py --bt tdx_data/bt_realrps_oneil.csv --signals ... --out tdx_data/odds_realrps_oneil.json --label "欧奈尔"
python analyze_odds.py --bt tdx_data/bt_realrps_trailing_be.csv ... --out tdx_data/odds_realrps_trailing_be.json --label "移动止盈+BE"
python analyze_odds.py --bt tdx_data/bt_realrps_oneil_be.csv   ... --out tdx_data/odds_realrps_oneil_be.json   --label "欧奈尔+BE"
```
- 赔率 = 平均盈利 / |平均亏损|（盈亏比）。`analyze_odds.py` 输出 整体/按年/按双RPS verdict/按形态/按离场原因。
- **BE（R6 盈利保护）已内置于 `backtest_v2_engine.run_backtest`**（2026-08-07 补齐）：参数 `be_stop` / `be_stop_th`（默认0.10）。
  实现方式：维护 `stop_price`（初始 `avg_entry*(1-8%)`），当 `ret >= be_stop_th` 时 `stop_price = max(stop_price, avg_entry)`（只上移），
  收盘价 `c <= stop_price` 即离场，reason 标 `BE止损-成本线`。`oneil` 与 `trailing` 两个分支都要改，漏一个会得到假阴性结论。
- 出场原因分布（回答"BE到底触没触发"）：
  `python -c` 按 `exit_reason` 分组计数 → 存 `tdx_data/exit_reason_dist.json`，`build_report.py` 会读取渲染。

### ③ 组合仓位方案网格（完整交叉 · 2026-08-14 定稿 v3）
**统一入口**：`python run_exit_grid_v3.py`（4 进程并行，180 组合）+ `python collect_v3_summary.py` + `python gen_v3_report.py`（180 组合报告 + 分段报告）。
- **必跑维度（占比规则固定动态净值×10%+无slot，不交叉）**：离场引擎（6）× 持仓上限（P555/P864/P1284）× 门控（G0/G1/G2/G3/GA）× R7-2（R0/R72）= 180 组合。
- **建仓金额一律 `--pos-size-mode nav`，不加占比约束**（唯一规则）。
- 组合定义见 `run_exit_grid_v3.py`；结果 `bt_exit_grid_v3/w*.csv` + stats `w*.json`（含 env 分段）+ 报告 `v3-grid-report-2026-08-14.html` + `segment-report-2026-08-14.html`。
- 引擎参数：`--be-stop` 开；`--r7-2-rank pool`（池内分位，新口径复核确认）；不启用量能控仓（已证跑输基准）。
- 单引擎快跑：`python portfolio_backtest.py --pool tdx_data/screener_pool_full_no_bj.csv --kline-dir tdx_data/kline_v2_2010 --index tdx_data/kline_index_2010/000001.csv --engine adaptive --signals-in tdx_data/signals_2010_2026_realrps.csv --trend-n 8 --range-n 6 --weak-n 4 --be-stop --mid-signal --mid-indexes 000001,399106 --pos-size-mode nav [--r7 2 --r7-rs250 0 --r7-rs120 0 --r7-2-rank pool] --stats-out s.json --out out.csv`

### ④ 报告
`python build_report.py` → `回测报告_2023_2025_真实RPS.html`（自包含：19条净值曲线SVG + **带BE/无BE赔率对照表** + 出场原因分布 + 分组拆解 + 方案对比表）。

## 已知结论（2026-08-14 新口径实测 · 旧结论全部作废）

> ⚠️ **2026-08-14 口径修正**：旧信号（池内分位 RPS）错误，此前所有"dr 最优"结论（+909%/+1266%）作废。以下为新口径（全市场分位）结论：

- **新口径 180 组合（2011-2026）引擎最优**：**adaptive（组合A+250日）10/15 子组合最优**（dr 0/15），TOP1 = adaptive·8-6-4·G2·R72 **+609.5%**（胜率 49.6%/赔率 2.36/3438 笔）；dr 同骨架 +318.0%。
- **稳健性复核（6引擎 × 2分段）**：验证段 2016-2026 adaptive **+1066.2%** vs dr +525.7%（+540pp）、peak +592.2%；胜率 50.6%/赔率 2.45 全面占优 → **adaptive 反超稳健**（非 2025 单年）。
- **分段画像（180 组合全部"牛市增强器"）**：牛段（2014-15/2017/2019-21/2024-26）adaptive 平均 +1044%（dr +588%）；熊段（2011-12/2018/2022）两者相近（-42% vs -39%）；震荡段均亏。→ adaptive 领先**全部来自牛市段爆发力**，非熊市更抗跌。
- **门控 G2（2指数）**：新口径下仍最优（熊市减损工具）；**持仓 8-6-4** 牛市段最优。
- **R7-2 腾位排序 = 池内分位（方案B 维持）**：新口径验证段 adaptive pool +1066% vs market +947%（+120pp），dr 亦 pool 优。
- **环境分段（2026-08-14 引擎新增 env 输出）**：adaptive 趋势市胜率 50.5%/均收益 +2.61% 全场最高，弱势市仍正收益（dr -3.72%）。

### BE(R6) 规则实测影响（关键结论，勿再重复踩坑）
| 口径 | 胜率 | 赔率 | 均收益 | 均亏损 | BE触发 |
|---|---|---|---|---|---|
| 移动止盈·无BE | 38.13% | 3.63 | +5.71% | -10.05% | — |
| 移动止盈·带BE | 37.93% | **3.64** | +5.63% | -8.88% | 219笔(8.8%) |
| 欧奈尔固定·无BE | 38.37% | 2.63 | +3.83% | -9.78% | — |
| 欧奈尔固定·带BE | 33.35% | **3.34** | +3.56% | -7.98% | 448笔(18.0%) |

- **移动止盈下 BE 近乎冗余**：回撤10%减半线 ≈ 1.10×0.90 = 0.99 已贴成本线，BE 与移动止盈高度重叠 → 赔率 3.63→3.64 几乎不动。
- **固定目标止盈下 BE 是必要补丁**：赔率 2.63→3.34 显著改善，-8%深亏笔数 1457→1188（少亏269笔），代价是胜率降 5pp（小赚单被锁成本）。
- **组合层面 BE 触发≈0**：账户级 `portfolio_backtest.py` 里 peak-10% 减半先于成本线触发，18方案 BE 开关对净值无差异。
- 落地口径：实盘用 Al Brooks 移动止盈时 BE 只是心理保险；若改用固定目标价（事件驱动/套利仓）**必须挂 BE**。

## 基本面过滤层（**已实装** 2026-08-08 · 用户选定 quality_floor 预设）

> 背景：2486 个技术信号（RPS强度+形态+趋势）混入大量低质量信号——陶博士基本面条目（C18-C23 / C1 / C2）在历史回测中整体缺席。本层把锚定层已有条件**实装**进回测链路（`fundamental_filter.py`，全部引用锚定阈值）。

### 两套预设（可复现，命令行 `--preset`）
| 预设 | 硬门槛 | 其余因子 | 保留率 | 用途 |
|---|---|---|---|---|
| `strict`（忠实陶博士六层全硬） | F0全硬 + F1-1强制≥25% + F2-1 ROE≥15% + F0-4现金流≥50% + PEG≤1 | 仅 L3 加分 | **0.5%（12个）** | 最贴合方案，但样本过小无法重跑回测 |
| `quality_floor`（**用户选定**） | **盈利(TTM不亏) + ROE≥10%** | F0-2/F0-3/F0-4/F0-1扣非/L1成长/PEG **全部转加分** | **22.0%（547个：A=406/B=141）** | 命中"减噪"目标，A档全权/B半仓可重跑 |

> ⚠️ **关键校准发现**：2023-2025 的动量/RPS 信号绝大多数集中在**低 ROE 主题炒作票**（AI/半导体/机器人/商业航天），信号时点 ROE<15% 高达 90%。忠实六层全硬仅留 0.5%，无统计意义；故用户拍板用 `quality_floor`（盈利+ROE≥10%）保留 22%，仍有"质量内核"。

### 六层结构（漏斗，阈值零发明）
- **L0 财务硬排除**：F0-1 非亏损(TTM净利>0)；F0-2 扣非同比≥-10%；F0-3 商誉/净资产<30%；F0-4 经营现金流/净利≥50%。（quality_floor 下除 F0-1 非亏外均降为加分）
- **L1 成长性**：F1-1 单季扣非同比≥25%(C19)；F1-2 三年年报复合≥20%(C20)；F1-3 营收同比≥15%。（quality_floor 下全降为加分，不再强制"三过二"）
- **L2 盈利质量**：F2-1 ROE≥15%(strict)/≥10%(quality_floor) 硬门槛，加分线 20%/15%；F2-2 毛利率≥30% 加分
- **L3 机构认同（加分）**：F3-1 基金≥3%(C1)；F3-2 北向市值≥3000万(C2)
- **L4 估值**：F4-2 PEG≤1(C21) 硬(strict)/加分(quality_floor)

### 分档规则
硬门槛全过 → 审美分（加分项各1分：F0-2正增/F0-3低商誉/F0-4现金流好/F0-1扣非正/F1-1/F1-2/F1-3/F2-1高ROE/F2-2毛利率/F3-1/F3-2/F4-2 PEG≤1）：
- **A档** ≥5分：全权交易 ｜ **B档** 3-4分：组合权重 ×0.5 ｜ **C档** ≤2分：剔除

### 数据源与时点（防未来函数）
- 财报 `fundamental_history.csv`（512只/9204行/19报告期）：westock-data finance 接口拉取，用真实 `InfoPublDate` asof（缺失披露日0%）
- 机构/股本 `fund_data_full.csv`：asof `report_date`（⚠️ 以2025年为主，2023-2024 信号缺 L3 数据）
- 市值 = 信号日收盘价(kline_v2) × 总股本(fund_data)，为 PEG 代理值
- 分档 `signals_filtered_{preset}.csv`，统计 `filter_stats_{preset}.json`

### 回测对比结果（compare_fund_filter.py · 复用 bt_realrps_*.csv 按 A/B 筛选）
四模式（trailing/oneil/±BE）**一致提升**：质量地板 A+B 胜率 38.1%→40.6%、单笔均值 +5.71%→+5.88%(trailing)，信号量砍 78%（2486→547）。
- **A档**是真正质量内核：胜率 43.1%、均值 +7.48%、赔率 3.71(trailing)，全面优于全样本 → "A全权"验证
- **B档跑输全样本**：胜率 33%、均值 +1.3% → "B半仓"合理，甚至可考虑仅做 A 档
- 结论：2023-2025 动量策略收益来自少数高质量突破票，多数低质量主题信号是噪声；基本面层在**不牺牲收益下大幅降频**，契合陶博士"强势股+基本面优秀"

### 已知实现偏差（与方案文档不一致，透明披露）
1. **L3 机构认同**：历史基金/北向逐季数据不可回溯（fund_data_full 以2025为主），降级为纯加分且仅覆盖2025信号
2. **F4-1 细分行业龙头(C23)**：缺申万行业营收排名数据，**未实装**
3. **市值/PEG**：信号日收盘价×股本 近似总市值（代理值）
4. 原预期 600-900/胜率≥45%；实际 quality_floor 547/40.6%，**保留率达标，胜率略低于45%目标但仍高于全样本**

## 依赖
- `taobo-O'Neil/references/rps_lookup.py`（**本地RPS真实取数 · 由陶博士选股 skill 拥有，本流水线复用，禁止另立副本**；需通达信 extdata 已刷新）
- `deliverables/taobo-daily/backtest_v2_engine.py`（信号/形态/单股回测核心）
- `deliverables/taobo-daily/portfolio_backtest.py`（组合账户模拟）
