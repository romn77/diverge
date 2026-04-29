# 计划：添加 akshare 和 tushare A 股数据源（v2）

## Context

当前 Diverge 主要围绕美股数据源（yfinance/alpha_vantage）设计。
目标是新增 A 股能力，并且不破坏现有工具接口与路由逻辑。

本版本聚焦三项关键修正：

1. 保持单一工具分类体系，不引入 `cn_*` 分类分叉
2. 路由时不再通过 `args[0]` 猜 ticker，改为显式参数解析
3. 引入统一 vendor 异常语义，fallback 不再只对 Alpha Vantage 生效

---

## 现有架构要点（修正版）

- **路由中心**：`diverge/dataflows/interface.py` 的 `route_to_vendor()`
- **配置中心**：`diverge/default_config.py` 的 `data_vendors` + `tool_vendors`
- **工具分类**：固定 4 类 `core_stock_apis / technical_indicators / fundamental_data / news_data`
- **返回类型约束**：现有接口约束是“返回 `str`”，不要求统一为 CSV
- **现有方法签名保持不变**：
  - `get_stock_data(symbol, start_date, end_date) -> str`
  - `get_indicators(symbol, indicator, curr_date, look_back_days) -> str`
  - `get_fundamentals(ticker, curr_date) -> str`
  - `get_balance_sheet/get_cashflow/get_income_statement(ticker, freq, curr_date) -> str`
  - `get_news(ticker, start_date, end_date) -> str`
  - `get_global_news(curr_date, look_back_days, limit) -> str`
  - `get_insider_transactions(ticker) -> str`

---

## 设计原则

1. **单一分类，多市场路由**
   - 分类只保留现有 4 类
   - CN/US 作为路由维度处理，不复制一套 `cn_*` 分类

2. **先解析方法参数，再判定市场**
   - 每个 method 定义 ticker 参数位（或无 ticker）
   - `get_global_news` 等无 ticker 方法不参与 ticker 市场识别

3. **统一异常语义**
   - vendor 内部异常统一映射为公共异常类型
   - 路由层只根据异常语义判断“切换下一 vendor / 直接失败”

---

## 新增文件

| 文件 | 职责 |
|------|------|
| `dataflows/cn_market_utils.py` | A 股 ticker 识别与标准化、日期和列名标准化工具 |
| `dataflows/vendor_errors.py` | 统一异常定义（可重试、鉴权、能力不支持、数据为空） |
| `dataflows/akshare_stock.py` | A 股行情 |
| `dataflows/akshare_indicator.py` | A 股技术指标（复用 stockstats 计算） |
| `dataflows/akshare_fundamentals.py` | A 股财务数据 |
| `dataflows/akshare_news.py` | A 股新闻/公告（能力可选） |
| `dataflows/akshare.py` | akshare dispatcher |
| `dataflows/tushare_stock.py` | A 股行情 |
| `dataflows/tushare_indicator.py` | A 股技术指标 |
| `dataflows/tushare_fundamentals.py` | A 股财务数据（优先） |
| `dataflows/tushare_news.py` | A 股新闻/公告（能力可选） |
| `dataflows/tushare.py` | tushare dispatcher |

---

## 修改文件与关键改动

### `dataflows/interface.py`

```python
# 1) 方法参数解析配置
METHOD_ARG_SCHEMA = {
    "get_stock_data": {"symbol_arg": "symbol", "pos": 0},
    "get_indicators": {"symbol_arg": "symbol", "pos": 0},
    "get_fundamentals": {"symbol_arg": "ticker", "pos": 0},
    "get_balance_sheet": {"symbol_arg": "ticker", "pos": 0},
    "get_cashflow": {"symbol_arg": "ticker", "pos": 0},
    "get_income_statement": {"symbol_arg": "ticker", "pos": 0},
    "get_news": {"symbol_arg": "ticker", "pos": 0},
    "get_insider_transactions": {"symbol_arg": "ticker", "pos": 0},
    "get_global_news": {"symbol_arg": None, "pos": None},  # 无 ticker
}

# 2) 统一入口：解析参数 -> 识别市场 -> 选择 vendor 列表
def resolve_market_and_symbol(method: str, args, kwargs):
    ...
    # return market("cn"/"us"/"global"), normalized_args, normalized_kwargs

# 3) 统一异常驱动 fallback
RETRYABLE_ERRORS = (VendorRetryableError, AlphaVantageRateLimitError)

def route_to_vendor(method: str, *args, **kwargs):
    market, args2, kwargs2 = resolve_market_and_symbol(method, args, kwargs)
    vendors = build_vendor_chain(method, market)  # 配置优先 + 可用 vendor 补全
    for vendor in vendors:
        try:
            return VENDOR_METHODS[method][vendor](*args2, **kwargs2)
        except RETRYABLE_ERRORS:
            continue
    raise RuntimeError(f"No available vendor for '{method}' in market='{market}'")
```

### `default_config.py`

```python
DEFAULT_CONFIG = {
    "market": "auto",  # auto/us/cn
    "data_vendors": {
        "core_stock_apis": "yfinance,alpha_vantage",
        "technical_indicators": "yfinance,alpha_vantage",
        "fundamental_data": "yfinance,alpha_vantage",
        "news_data": "yfinance,alpha_vantage",
    },
    "market_overrides": {
        "cn": {
            "core_stock_apis": "akshare,tushare",
            "technical_indicators": "akshare,tushare",
            "fundamental_data": "tushare,akshare",
            "news_data": "akshare,yfinance",
        },
        "us": {
            "core_stock_apis": "yfinance,alpha_vantage",
            "technical_indicators": "yfinance,alpha_vantage",
            "fundamental_data": "yfinance,alpha_vantage",
            "news_data": "yfinance,alpha_vantage",
        },
    },
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
}
```

---

## `cn_market_utils.py` 关键函数（修正版）

```python
def parse_and_normalize_cn_ticker(symbol: str) -> dict:
    """
    输入可接受: 600519 / sh600519 / 600519.SH / SZ000001
    输出:
      raw: "600519"
      exchange: "SH" | "SZ"
      akshare: "sh600519"
      tushare: "600519.SH"
    """

def detect_market(symbol: str) -> str:
    """返回 'cn' | 'us' | 'unknown'"""

def dataframe_to_standard_string(df: pd.DataFrame, title: str) -> str:
    """统一 DataFrame 输出格式，返回 str（CSV 或可读文本均可）"""
```

---

## 实施顺序（修正版）

1. **公共层先行**
   - `vendor_errors.py`
   - `cn_market_utils.py`
   - `interface.py` 中 `resolve_market_and_symbol()` 与异常驱动 fallback

2. **Phase 1: 先交付高价值能力**
   - `akshare_stock.py` + `tushare_stock.py`
   - `tushare_fundamentals.py` + `akshare_fundamentals.py`
   - 目标是 `get_stock_data/get_fundamentals/get_balance_sheet/get_cashflow/get_income_statement` 可用

3. **Phase 2: 技术指标**
   - 统一走“OHLCV + stockstats”计算路径，减少供应商差异

4. **Phase 3: 新闻与内幕（能力可选）**
   - 若源稳定且权限可满足再纳入默认 fallback 链

---

## 关键实现细节

### 1) Ticker 识别与格式标准化

- 不使用 `lstrip("SH")` 这类不安全写法
- 统一正则解析前缀/后缀，再映射为各 vendor 需要的格式

### 2) 异常语义

- `VendorRetryableError`：超时、临时网络错误、频控，可 fallback
- `VendorAuthError`：token 缺失或权限不足，不应盲目重试同 vendor
- `VendorNotSupportedError`：该方法在该 vendor 不支持
- `VendorDataEmptyError`：数据为空（由业务决定是否 fallback）

### 3) 输出一致性

- 新 vendor 返回 `str` 即可，不强制 CSV
- 同一 method 尽量保持可读风格一致，便于 LLM 工具消费

### 4) 依赖管理

- 将 `akshare`、`tushare` 写入 `pyproject.toml`
- 文档保留环境变量要求：`TUSHARE_TOKEN`

---

## 验证方案（修正版）

1. **Contract Tests（离线）**
   - mock vendor SDK 返回，验证每个 method 始终返回 `str`
   - 验证 `resolve_market_and_symbol()` 在各 method 上解析正确

2. **路由测试**
   - `600519`/`600519.SH` -> CN 路由
   - `AAPL` -> US 路由
   - `get_global_news("2024-06-01", ...)` 不触发 ticker 识别误判

3. **Fallback 测试**
   - 触发 `VendorRetryableError` 时切换下一 vendor
   - 触发 `VendorAuthError` 时按策略快速失败或跳过当前 vendor

4. **在线 Smoke Tests（少量）**
   - 在有网络与 token 环境下做最小真实调用，验证端到端可用

5. **端到端**
   - CLI 跑 A 股样例并检查报告是否完整：
   - `diverge analyze --ticker 600519 --date 2024-06-01`
