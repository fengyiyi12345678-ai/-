# Equity Research Copilot

一个本地运行的中文投研建模工具，覆盖从财报清洗、收入结构分析、未来5年预测、
DCF 估值、敏感性分析、可比公司估值到中文 Markdown 投研报告与 Excel 模型导出的
完整流程。

## 1. 项目介绍

- **项目名**：`equity_research_copilot`
- **目标用户**：股票研究员、买方/卖方分析师、独立投资者
- **核心理念**：
  1. **数据真实**：缺失数据一律显示为 `N/A`，从不编造。
  2. **可插拔数据源**：在线源 + 上传源同一接口，互为兜底。
  3. **本地优先**：不依赖任何托管服务，所有计算和文件均在本地完成。
  4. **可审计**：保留原始字段映射、生成完整 Excel 模型、可复现的中文报告。

## 2. 安装方法

```bash
git clone <repo>
cd equity_research_copilot

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # 按需填写公开数据源地址；不需要也可不填
```

> 注意：本项目**绝不**在代码中硬编码任何 API Key，所有凭证均来自 `.env`。

## 3. 运行方法

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

### 单元测试

```bash
pytest -q
```

## 4. 数据上传格式

所有上传文件均支持 `.csv` / `.xlsx`。`data/sample/` 目录下提供了示例。

### 4.1 利润表 `income_statement.csv`

| 列名 | 含义 |
|---|---|
| `year` | 财年 |
| `revenue` | 营业收入 |
| `cost_of_revenue` | 营业成本 |
| `gross_profit` | 毛利（可缺省，系统会用 `revenue - cost_of_revenue` 推导） |
| `operating_income` | 经营利润 |
| `net_income` | 净利润 |

### 4.2 资产负债表 `balance_sheet.csv`

| 列名 | 含义 |
|---|---|
| `year` | 财年 |
| `cash` | 货币资金 |
| `total_debt` | 总有息负债 |
| `total_assets` | 总资产 |
| `total_liabilities` | 总负债 |
| `shareholders_equity` | 股东权益 |
| `diluted_shares` | 稀释股本（单位：百万股） |

### 4.3 现金流量表 `cash_flow.csv`

| 列名 | 含义 |
|---|---|
| `year` | 财年 |
| `operating_cash_flow` | 经营活动现金流 |
| `capex` | 资本开支（绝对值或负数均可） |
| `depreciation` | 折旧与摊销（可选） |

### 4.4 收入分部 `revenue_segments.csv`

```
year, segment, revenue, gross_profit, operating_profit
```

### 4.5 可比公司 `peer_companies.csv`

```
ticker, company_name, market_cap, revenue, net_income, ebitda, ev
```

字段说明：所有金额单位需保持一致（推荐统一使用百万）。

## 5. DCF 模型公式

```text
revenue_t          = revenue_(t-1) * (1 + growth_rate_t)
operating_income   = revenue * operating_margin
nopat              = operating_income * (1 - tax_rate)
depreciation       = revenue * depreciation_pct_revenue
capex              = revenue * capex_pct_revenue
change_in_nwc      = (revenue_t - revenue_(t-1)) * nwc_pct_revenue
free_cash_flow     = nopat + depreciation - capex - change_in_nwc

terminal_value     = final_year_fcf * (1 + g) / (wacc - g)
enterprise_value   = ΣPV(free_cash_flows) + PV(terminal_value)
equity_value       = enterprise_value - net_debt
fair_value/share   = equity_value / diluted_shares
```

- 单位统一为**百万**；股本单位为**百万股**。
- `WACC <= 永续增长率` 时模型会主动报错。

## 6. 可比公司估值方法

1. 自动计算 `P/S`、`P/E`、`EV/Sales`、`EV/EBITDA`。
2. 自动剔除：净利润为负的公司不参与 `P/E` 计算；EBITDA 为负的公司不参与 `EV/EBITDA`。
3. 使用 MAD（中位数绝对偏差）标注极端值，中位数估值默认基于剔除极端值后的样本。
4. 用 25 / 50 / 75 分位数倍数 × 目标公司指标得到低 / 中 / 高位估值区间。
5. EV 倍数会用 `净负债` 调整为权益价值，再除以稀释股本得到每股估值。
6. **样本不足 3 家公司**时会提示，仅作参考。

## 7. 敏感性分析

- WACC ± 1.5% × 永续增长率 ± 1.0%（5 × 5 矩阵）
- 收入增速 ± 3.0% × 经营利润率 ± 3.0%（5 × 5 矩阵）
- 输出每股公允价值；非法组合（如 WACC ≤ g）单元格显示 NaN。

## 8. 常见问题

**Q1：在线数据接口报错怎么办？**
A：本项目默认不内置任何商业数据接口。若 `.env` 未配置 `PUBLIC_DATA_PROVIDER_URL`
或接口请求失败，UI 会直接提示缺失字段，请改用上传方式（Upload）。

**Q2：金额单位用什么？**
A：统一**百万**（货币单位由用户决定，工具内只按数值处理）。

**Q3：缺失部分财报数据会怎样？**
A：缺失字段显示 `N/A`，对应模块跳过，并在风险提示中明示「数据缺失」。
其他可用模块仍正常运行。

**Q4：能 commit 的隐私数据吗？**
A：`data/raw/*` 与 `data/processed/*` 已默认加入 `.gitignore`。

## 9. 免责声明

> 本工具仅用于研究分析，所有结果基于用户输入的数据与假设，**不构成任何投资建议**。
> 投资有风险，入市需谨慎。
