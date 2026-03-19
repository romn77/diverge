# 计划 002: DCF与基本面价值分析

**创建日期**: 2026-03-18
**状态**: 待实施
**优先级**: 高
**参考**: [Anthropic Financial Services Plugins - Financial Analysis](https://github.com/anthropics/financial-services-plugins/tree/main/financial-analysis)

## 需求概述

为 TradingAgents 增加基本面价值分析能力，包括：
- DCF (Discounted Cash Flow) 现金流折现估值
- 财务比率分析（流动性、盈利能力、偿债能力）
- 估值模型（P/E, P/B, EV/EBITDA等）
- 敏感性分析和情景规划

## 参考架构分析

### Anthropic Financial-Services-Plugins 架构

根据GitHub参考项目，推荐的实现方式：

```
financial-analysis/
├── .mcp.json              # MCP协议配置
├── skills/                # 分析技能模块
│   ├── dcf_analysis.py   # DCF估值
│   ├── ratio_analysis.py # 财务比率
│   ├── valuation.py      # 估值模型
│   └── sensitivity.py    # 敏感性分析
└── commands/             # CLI命令接口
```

**核心特点**:
1. **MCP (Model Context Protocol)**: 标准化的工具调用接口
2. **模块化设计**: 每个分析类型独立实现
3. **Claude集成**: 支持自然语言查询和分析

## 实施方案

### 架构设计

```
tradingagents/
├── fundamental/              # 新增基本面分析模块
│   ├── __init__.py
│   ├── dcf.py               # DCF模型
│   ├── ratios.py            # 财务比率
│   ├── valuation.py         # 估值方法
│   ├── data_fetcher.py      # 数据获取层
│   └── models.py            # 数据模型
├── analysts/                # 现有分析师模块
│   └── fundamental_analyst.py  # 新增基本面分析师
└── runner.py                # 扩展分析流程
```

### 方案一: 集成为新的Analyst（推荐）

**设计理念**: 将基本面分析作为一个新的"Fundamental Analyst"角色，与现有的Technical Analyst等并列。

#### 1. 创建 FundamentalAnalyst

**文件**: `tradingagents/analysts/fundamental_analyst.py`

```python
from dataclasses import dataclass
from typing import Dict, Any

from tradingagents.fundamental.dcf import DCFAnalyzer
from tradingagents.fundamental.ratios import RatioAnalyzer
from tradingagents.fundamental.valuation import ValuationAnalyzer
from tradingagents.fundamental.data_fetcher import FinancialDataFetcher

@dataclass
class FundamentalAnalyst:
    """基本面分析师 - 专注于公司价值评估"""

    name: str = "Fundamental"
    description: str = "DCF估值与财务分析专家"

    def __init__(self, llm_client):
        self.llm = llm_client
        self.data_fetcher = FinancialDataFetcher()
        self.dcf_analyzer = DCFAnalyzer()
        self.ratio_analyzer = RatioAnalyzer()
        self.valuation_analyzer = ValuationAnalyzer()

    async def analyze(self, ticker: str, analysis_date: str) -> Dict[str, Any]:
        """
        执行完整的基本面分析

        Returns:
            {
                "dcf_valuation": {...},
                "ratios": {...},
                "multiples": {...},
                "fair_value_estimate": float,
                "recommendation": str
            }
        """
        # 1. 获取财务数据
        financial_data = await self.data_fetcher.fetch_financial_statements(
            ticker, periods=5
        )

        # 2. DCF估值
        dcf_result = self.dcf_analyzer.calculate(
            cash_flows=financial_data['cash_flows'],
            wacc=0.10,  # 从LLM或用户配置获取
            terminal_growth_rate=0.03
        )

        # 3. 财务比率分析
        ratios = self.ratio_analyzer.calculate_all_ratios(
            income_statement=financial_data['income_statement'],
            balance_sheet=financial_data['balance_sheet'],
            cash_flow=financial_data['cash_flow']
        )

        # 4. 可比公司估值
        multiples = self.valuation_analyzer.calculate_multiples(
            ticker=ticker,
            financial_data=financial_data
        )

        # 5. LLM综合分析
        analysis_prompt = self._build_analysis_prompt(
            ticker, dcf_result, ratios, multiples
        )

        llm_insight = await self.llm.generate(analysis_prompt)

        return {
            "dcf_valuation": dcf_result,
            "ratios": ratios,
            "multiples": multiples,
            "market_price": financial_data['current_price'],
            "fair_value_estimate": dcf_result['enterprise_value_per_share'],
            "upside_downside": self._calculate_upside(
                dcf_result['enterprise_value_per_share'],
                financial_data['current_price']
            ),
            "llm_insight": llm_insight,
            "recommendation": self._generate_recommendation(dcf_result, ratios)
        }

    def _build_analysis_prompt(self, ticker, dcf, ratios, multiples):
        return f"""
        作为资深价值投资分析师，请基于以下数据对 {ticker} 进行深度分析：

        ## DCF估值结果
        {dcf}

        ## 财务比率
        {ratios}

        ## 估值倍数
        {multiples}

        请提供：
        1. 估值合理性评估
        2. 财务健康度评价
        3. 关键风险因素
        4. 投资建议（买入/持有/卖出）
        """
```

#### 2. DCF分析核心模块

**文件**: `tradingagents/fundamental/dcf.py`

```python
from typing import List, Dict, Any
import numpy as np

class DCFAnalyzer:
    """DCF现金流折现模型"""

    def calculate(
        self,
        cash_flows: List[float],
        wacc: float,
        terminal_growth_rate: float,
        shares_outstanding: float
    ) -> Dict[str, Any]:
        """
        计算DCF估值

        Args:
            cash_flows: 自由现金流列表（历史+预测）
            wacc: 加权平均资本成本
            terminal_growth_rate: 永续增长率
            shares_outstanding: 流通股本

        Returns:
            {
                "present_value_fcf": float,
                "terminal_value": float,
                "enterprise_value": float,
                "equity_value": float,
                "value_per_share": float,
                "assumptions": {...},
                "sensitivity_analysis": {...}
            }
        """
        # 预测未来5年现金流（简化示例）
        forecast_years = 5
        projected_fcf = self._project_cash_flows(cash_flows, forecast_years)

        # 计算现值
        pv_fcf = sum(
            fcf / ((1 + wacc) ** (i + 1))
            for i, fcf in enumerate(projected_fcf)
        )

        # 终值计算
        terminal_fcf = projected_fcf[-1] * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (wacc - terminal_growth_rate)
        pv_terminal_value = terminal_value / ((1 + wacc) ** forecast_years)

        # 企业价值
        enterprise_value = pv_fcf + pv_terminal_value

        # 股权价值 = 企业价值 - 净债务
        # (这里需要从资产负债表获取)
        equity_value = enterprise_value  # 简化

        # 每股价值
        value_per_share = equity_value / shares_outstanding

        # 敏感性分析
        sensitivity = self._sensitivity_analysis(
            projected_fcf, wacc, terminal_growth_rate, shares_outstanding
        )

        return {
            "present_value_fcf": pv_fcf,
            "present_value_terminal": pv_terminal_value,
            "terminal_value": terminal_value,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "enterprise_value_per_share": value_per_share,
            "assumptions": {
                "wacc": wacc,
                "terminal_growth_rate": terminal_growth_rate,
                "forecast_years": forecast_years,
                "projected_fcf": projected_fcf
            },
            "sensitivity_analysis": sensitivity
        }

    def _project_cash_flows(self, historical_cf: List[float], years: int) -> List[float]:
        """基于历史数据预测未来现金流"""
        if len(historical_cf) < 3:
            raise ValueError("需要至少3年历史数据")

        # 简单的线性增长预测（实际应用中可以用更复杂的模型）
        growth_rates = [
            (historical_cf[i] - historical_cf[i-1]) / historical_cf[i-1]
            for i in range(1, len(historical_cf))
        ]
        avg_growth = np.mean(growth_rates)

        # 保守预测：增长率逐年递减
        projected = []
        last_cf = historical_cf[-1]
        for year in range(years):
            growth = avg_growth * (0.9 ** year)  # 每年递减10%
            last_cf = last_cf * (1 + growth)
            projected.append(last_cf)

        return projected

    def _sensitivity_analysis(
        self,
        cash_flows: List[float],
        base_wacc: float,
        base_growth: float,
        shares: float
    ) -> Dict[str, Any]:
        """敏感性分析：WACC和终值增长率的影响"""
        wacc_range = [base_wacc - 0.02, base_wacc, base_wacc + 0.02]
        growth_range = [base_growth - 0.01, base_growth, base_growth + 0.01]

        sensitivity_matrix = []
        for wacc in wacc_range:
            row = []
            for growth in growth_range:
                result = self.calculate(cash_flows, wacc, growth, shares)
                row.append(result['enterprise_value_per_share'])
            sensitivity_matrix.append(row)

        return {
            "wacc_range": wacc_range,
            "growth_range": growth_range,
            "value_matrix": sensitivity_matrix
        }
```

#### 3. 财务比率分析

**文件**: `tradingagents/fundamental/ratios.py`

```python
class RatioAnalyzer:
    """财务比率分析"""

    def calculate_all_ratios(
        self,
        income_statement: dict,
        balance_sheet: dict,
        cash_flow: dict
    ) -> dict:
        """计算所有关键财务比率"""

        return {
            "liquidity": self._liquidity_ratios(balance_sheet),
            "profitability": self._profitability_ratios(income_statement, balance_sheet),
            "leverage": self._leverage_ratios(balance_sheet),
            "efficiency": self._efficiency_ratios(income_statement, balance_sheet),
            "cash_flow": self._cash_flow_ratios(cash_flow, income_statement)
        }

    def _liquidity_ratios(self, bs: dict) -> dict:
        """流动性比率"""
        return {
            "current_ratio": bs['current_assets'] / bs['current_liabilities'],
            "quick_ratio": (
                (bs['current_assets'] - bs['inventory']) /
                bs['current_liabilities']
            ),
            "cash_ratio": bs['cash'] / bs['current_liabilities']
        }

    def _profitability_ratios(self, is_: dict, bs: dict) -> dict:
        """盈利能力比率"""
        return {
            "gross_margin": is_['gross_profit'] / is_['revenue'],
            "operating_margin": is_['operating_income'] / is_['revenue'],
            "net_margin": is_['net_income'] / is_['revenue'],
            "roa": is_['net_income'] / bs['total_assets'],
            "roe": is_['net_income'] / bs['shareholders_equity'],
            "roic": is_['operating_income'] / (bs['total_assets'] - bs['current_liabilities'])
        }

    def _leverage_ratios(self, bs: dict) -> dict:
        """杠杆比率"""
        return {
            "debt_to_equity": bs['total_debt'] / bs['shareholders_equity'],
            "debt_to_assets": bs['total_debt'] / bs['total_assets'],
            "equity_multiplier": bs['total_assets'] / bs['shareholders_equity'],
            "interest_coverage": bs['ebit'] / bs['interest_expense']
        }

    def _efficiency_ratios(self, is_: dict, bs: dict) -> dict:
        """运营效率比率"""
        return {
            "asset_turnover": is_['revenue'] / bs['total_assets'],
            "inventory_turnover": is_['cogs'] / bs['inventory'],
            "receivables_turnover": is_['revenue'] / bs['accounts_receivable']
        }

    def _cash_flow_ratios(self, cf: dict, is_: dict) -> dict:
        """现金流比率"""
        return {
            "operating_cash_flow_ratio": cf['operating_cash_flow'] / is_['revenue'],
            "free_cash_flow": cf['operating_cash_flow'] - cf['capex'],
            "cash_flow_to_net_income": cf['operating_cash_flow'] / is_['net_income']
        }
```

#### 4. 数据获取层

**文件**: `tradingagents/fundamental/data_fetcher.py`

```python
import yfinance as yf
from typing import Dict, Any

class FinancialDataFetcher:
    """财务数据获取"""

    async def fetch_financial_statements(
        self,
        ticker: str,
        periods: int = 5
    ) -> Dict[str, Any]:
        """
        获取财务报表数据

        数据源选项：
        1. yfinance (免费但有限制)
        2. Alpha Vantage (需要API key)
        3. Financial Modeling Prep (推荐)
        4. 自建数据库
        """
        stock = yf.Ticker(ticker)

        # 获取财务报表
        income_stmt = stock.financials
        balance_sheet = stock.balance_sheet
        cash_flow = stock.cashflow

        # 获取当前价格
        current_price = stock.info.get('currentPrice', 0)
        shares_outstanding = stock.info.get('sharesOutstanding', 0)

        return {
            "income_statement": self._parse_income_statement(income_stmt),
            "balance_sheet": self._parse_balance_sheet(balance_sheet),
            "cash_flow": self._parse_cash_flow(cash_flow),
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "cash_flows": self._extract_free_cash_flows(cash_flow, periods)
        }

    def _extract_free_cash_flows(self, cash_flow_df, periods: int) -> list:
        """提取历史自由现金流"""
        try:
            operating_cf = cash_flow_df.loc['Operating Cash Flow'].values[:periods]
            capex = cash_flow_df.loc['Capital Expenditure'].values[:periods]
            return [float(ocf + capex) for ocf, capex in zip(operating_cf, capex)]
        except KeyError:
            return []

    def _parse_income_statement(self, df) -> dict:
        """解析利润表"""
        # 实现数据提取逻辑
        pass

    def _parse_balance_sheet(self, df) -> dict:
        """解析资产负债表"""
        pass

    def _parse_cash_flow(self, df) -> dict:
        """解析现金流量表"""
        pass
```

#### 5. 集成到现有流程

**修改**: `tradingagents/runner.py`

```python
from tradingagents.analysts.fundamental_analyst import FundamentalAnalyst

# 在 ANALYST_ORDER 中添加
ANALYST_ORDER = [
    ("Fundamental", AnalystType.FUNDAMENTAL),  # 新增
    ("Technical", AnalystType.TECHNICAL),
    ("Market", AnalystType.MARKET),
    # ...
]

# 在分析流程中调用
async def run_analysis_streaming(request: AnalysisRequest, output_dir: Path):
    # ...
    if AnalystType.FUNDAMENTAL in request.analysts:
        fundamental_analyst = FundamentalAnalyst(llm_client)
        result = await fundamental_analyst.analyze(
            request.ticker,
            request.analysis_date
        )
        yield AnalysisProgress(
            stage="Analysts",
            current_agent="Fundamental",
            message="DCF估值完成",
            data=result
        )
```

#### 6. 前端展示

**新增组件**: `frontend/components/FundamentalAnalysis.tsx`

```tsx
interface DCFResult {
  enterprise_value_per_share: number;
  present_value_fcf: number;
  terminal_value: number;
  sensitivity_analysis: {
    wacc_range: number[];
    growth_range: number[];
    value_matrix: number[][];
  };
}

export function DCFValuationCard({ data }: { data: DCFResult }) {
  return (
    <div className="rounded-3xl border border-[var(--border)] bg-white p-6">
      <h3 className="text-xl font-bold">DCF估值分析</h3>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <MetricCard
          label="目标价"
          value={`$${data.enterprise_value_per_share.toFixed(2)}`}
          trend="up"
        />
        <MetricCard
          label="现金流现值"
          value={`$${(data.present_value_fcf / 1e9).toFixed(2)}B`}
        />
        <MetricCard
          label="终值"
          value={`$${(data.terminal_value / 1e9).toFixed(2)}B`}
        />
      </div>

      <SensitivityMatrix data={data.sensitivity_analysis} />
    </div>
  );
}
```

---

### 方案二: MCP协议集成（高级方案）

**适用场景**: 需要与Claude Desktop或其他AI工具深度集成

参考Anthropic的financial-analysis插件架构：

1. **创建 MCP Server**:
   ```python
   # tradingagents/mcp_server.py
   from mcp import MCPServer, Tool

   server = MCPServer(name="tradingagents-fundamental")

   @server.tool()
   async def dcf_valuation(ticker: str, wacc: float = 0.10) -> dict:
       """执行DCF估值分析"""
       analyzer = DCFAnalyzer()
       # ... 实现
       return result

   @server.tool()
   async def ratio_analysis(ticker: str) -> dict:
       """计算财务比率"""
       # ... 实现
       return ratios
   ```

2. **配置文件**: `.mcp.json`
   ```json
   {
     "name": "tradingagents-fundamental",
     "description": "TradingAgents基本面分析工具",
     "version": "1.0.0",
     "tools": [
       {
         "name": "dcf_valuation",
         "description": "DCF现金流折现估值",
         "parameters": {
           "ticker": {"type": "string", "required": true},
           "wacc": {"type": "number", "default": 0.10}
         }
       }
     ]
   }
   ```

3. **Claude Desktop集成**: 用户可在Claude中直接调用

---

## 数据源方案

### 推荐数据源

1. **yfinance** (免费)
   - 优点: 免费，数据较全
   - 缺点: 不稳定，可能被限流

2. **Financial Modeling Prep** (推荐)
   - 免费层: 250 requests/day
   - 付费: $14/月
   - 数据质量高

3. **Alpha Vantage**
   - 免费: 5 API calls/minute
   - 财务报表数据完整

4. **Polygon.io**
   - 实时+历史数据
   - $249/月

**实施建议**: 先用yfinance原型验证，后续升级到FMP或Polygon

---

## Web界面集成

### 在报告查看器中展示

1. **新增标签页**: "基本面分析"
2. **可视化组件**:
   - DCF估值瀑布图
   - 敏感性热力图
   - 财务比率雷达图
   - 5年趋势图
3. **交互功能**:
   - 调整WACC和增长率
   - 实时重新计算估值
   - 对比历史估值

### API扩展

**新增端点**:
```python
@app.post("/api/fundamental/dcf")
async def calculate_dcf(ticker: str, params: DCFParams) -> dict:
    """实时DCF计算"""
    pass

@app.get("/api/fundamental/ratios/{ticker}")
async def get_ratios(ticker: str) -> dict:
    """获取财务比率"""
    pass
```

---

## 实施时间线

### Phase 1: 核心功能 (2-3周)
- [x] DCF基础模型
- [x] 财务比率计算
- [x] 数据获取层（yfinance）
- [x] 基本报告生成

### Phase 2: Analyst集成 (1-2周)
- [x] FundamentalAnalyst实现
- [x] 集成到分析流程
- [x] Markdown报告模板

### Phase 3: Web界面 (1-2周)
- [x] 前端可视化组件
- [x] API端点
- [x] 交互式参数调整

### Phase 4: 高级功能 (可选)
- [ ] 敏感性分析可视化
- [ ] 可比公司分析
- [ ] MCP协议支持
- [ ] 多数据源支持

---

## 成功标准

- [ ] 支持DCF估值计算
- [ ] 自动获取财务数据
- [ ] 计算15+关键财务比率
- [ ] 敏感性分析
- [ ] LLM生成分析报告
- [ ] Web界面展示
- [ ] 准确率达到行业标准（vs. Bloomberg Terminal）

---

## 风险和限制

1. **数据质量**: 免费数据源可能不准确
2. **计算复杂性**: DCF需要大量假设，结果有不确定性
3. **实时性**: 财务报表季度更新，不适合短期交易
4. **合规性**: 确保不违反数据使用协议

---

## 参考资源

- [Damodaran DCF模型](http://pages.stern.nyu.edu/~adamodar/)
- [Anthropic Financial Plugins](https://github.com/anthropics/financial-services-plugins)
- [MCP协议文档](https://modelcontextprotocol.io)
- [Financial Modeling Prep API](https://financialmodelingprep.com/developer/docs)

---

## 下一步行动

1. **技术选型决策**:
   - [ ] 确定数据源
   - [ ] 选择方案一或方案二
   - [ ] 评估是否需要MCP集成

2. **原型开发**:
   - [ ] 实现基础DCF模块
   - [ ] 验证数据获取
   - [ ] 生成示例报告

3. **团队Review**:
   - [ ] 财务模型验证
   - [ ] 代码审查
   - [ ] 用户测试

需要讨论的问题：
- 希望支持哪些数据源？
- 是否需要实时计算功能？
- MCP集成的优先级？
