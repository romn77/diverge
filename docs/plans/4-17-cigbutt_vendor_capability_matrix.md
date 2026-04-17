# Cigbutt Vendor Capability Matrix

## 1. 目的

这份文档用于回答两个问题：

1. `cigbutt` prompt 里提到的能力，现有 `akshare` / `tushare` 官方文档是否已经有近似接口。
2. 这些能力在当前仓库里，哪些已经通过 `interface.py` 暴露给 agent，哪些还只是 vendor 有、但仓库没封装，哪些必须补充通用 web 工具。

这份矩阵的目标不是给出最终架构结论，而是先把边界划清：

- `vendor structure data`
- `repo wrapper coverage`
- `web-only / MCP-only capabilities`


## 2. 当前仓库基线

### 2.1 当前真正暴露给 agent 的数据方法

当前 `ToolNode` 和 `interface.py` 暴露的核心方法只有：

- `get_stock_data`
- `get_indicators`
- `get_fundamentals`
- `get_balance_sheet`
- `get_cashflow`
- `get_income_statement`
- `get_news`
- `get_global_news`
- `get_insider_transactions`

对应代码：

- `tradingagents/graph/trading_graph.py`
- `tradingagents/dataflows/interface.py`
- `tradingagents/agents/utils/core_stock_tools.py`
- `tradingagents/agents/utils/fundamental_data_tools.py`
- `tradingagents/agents/utils/news_data_tools.py`

### 2.2 当前 CN 市场默认 vendor 路由

当前默认配置中，A 股相关路由大致是：

- `core_stock_apis`: `akshare,tushare`
- `technical_indicators`: `akshare,tushare`
- `fundamental_data`: `tushare,akshare`
- `news_data`: `akshare,yfinance`

这意味着仓库已经默认承认：

- A 股价格/财务表可以优先走 `tushare` / `akshare`
- A 股资讯类能力当前更偏 `akshare`

但这不代表所有 `cigbutt` 需要的能力已经封装。


## 3. 结论先看

### 3.1 明确可以由 vendor 覆盖的大类

以下能力，`tushare` 和/或 `akshare` 官方文档里已经有近似接口：

- 最新价格、总市值、总股本、PB、股息率
- 三大报表和财务指标
- 前十大股东、前十大流通股东
- 实控人/控制关系
- 股东或高管增减持
- 分红、回购
- 主营业务构成
- 审计意见
- 公司公告索引
- 股权质押、担保等部分治理/风险字段

### 3.2 当前仓库的真实缺口

当前仓库的主要缺口不是 vendor 没数据，而是：

- `interface.py` 只注册了很少一部分方法
- `akshare_*` / `tushare_*` wrapper 只封了三表、基础指标、极少量资讯
- 很多适合 `cigbutt` 的接口还没有统一成 agent 可调用 tool

### 3.3 vendor 不能替代的部分

以下能力不能简单等同于 `akshare` / `tushare`：

- 通用联网搜索
- 任意网页抓取
- 页面正文抽取
- HTML 表格抽取
- 多网页来源的可追溯证据拼接

所以：

- 如果目标是 A 股 `cigbutt` v1，并且优先做结构化分析，`vendor wrapper` 路线可行
- 如果目标是 prompt 原文那种“网页发现 + 页面抓取 + 来源附录”的研究 agent，仍然需要 web/MCP 工具链


## 4. 能力对照表

| 能力类别 | `cigbutt` 需求 | Tushare 文档能力 | AkShare 文档能力 | 当前仓库状态 | 判断 |
| --- | --- | --- | --- | --- | --- |
| 市场快照 | 最新收盘价 | `daily_basic` 可配合行情接口 | `stock_value_em` / 历史行情接口 | 已有 `get_stock_data`，但没有单独“快照”接口 | vendor 有，建议补 wrapper |
| 市场快照 | 最新总市值 | `daily_basic.total_mv` | `stock_value_em.总市值` | 未暴露 | vendor 有，建议补 wrapper |
| 市场快照 | 最新总股本 | `daily_basic.total_share` | `stock_value_em.总股本` | 未暴露 | vendor 有，建议补 wrapper |
| 市场快照 | 最新 PB | `daily_basic.pb` | `stock_value_em.市净率` | 未暴露 | vendor 有，建议补 wrapper |
| 市场快照 | 最新股息率 TTM | `daily_basic.dv_ttm` | `stock_fhps_em` / `stock_fhps_detail_em` 可部分替代 | 未暴露 | Tushare 更适合做统一口径 |
| 财务提取 | 最近三年三表 | `income` / `balancesheet` / `cashflow` | `stock_financial_report_sina` 或东财三表 | 已有 `get_balance_sheet` / `get_cashflow` / `get_income_statement` | 已部分可用 |
| 财务提取 | 基础财务指标 | `fina_indicator` | 财务指标接口较多 | 已有 `get_fundamentals`，但字段较少 | 已部分可用，需增强 |
| 财务提取 | 主营业务构成 | `fina_mainbz` | `stock_zygc_em` / `stock_zyjs_ths` | 未暴露 | vendor 有，建议补 wrapper |
| 股东结构 | 前十大股东 | `top10_holders` | `stock_gdfx_top_10_em` 等 | 未暴露 | vendor 有，建议补 wrapper |
| 股东结构 | 前十大流通股东 | `top10_floatholders` | 数据字典显示支持 | 未暴露 | vendor 有，建议补 wrapper |
| 控制关系 | 实控人 / 控制类型 | 可从股东链条部分推断，但不是最直接 | `stock_hold_control_cninfo` | 未暴露 | AkShare 更适合做 wrapper |
| 控制关系 | 股本变动 / 控股变化 | 相关接口较分散 | `stock_share_change_cninfo` | 未暴露 | vendor 有，建议补 wrapper |
| 管理层行为 | 股东增减持 | `stk_holdertrade` | `stock_ggcg_em`、`stock_hold_management_detail_cninfo` | 当前 `get_insider_transactions` 在 CN 侧基本未实现 | vendor 有，建议重做而非沿用旧命名 |
| 资本回收 | 回购 | `repurchase` | 未看到稳定 A 股回购总表接口优于 Tushare | 未暴露 | Tushare 更适合做 wrapper |
| 资本回收 | 分红历史 | `dividend` | `stock_fhps_em` / `stock_fhps_detail_em` / `stock_dividend_cninfo` | 未暴露 | vendor 有，建议补 wrapper |
| 审计与治理 | 审计意见 / 审计所 | `fina_audit` | 可通过公告或个别接口旁路获取 | 未暴露 | Tushare 更适合做 wrapper |
| 公告检索 | 公告索引 / PDF URL | `anns_d` | `stock_zh_a_disclosure_report_cninfo` | 未暴露 | vendor 有，建议补 wrapper |
| 风险核查 | 股权质押 | `pledge_stat` / `pledge_detail` | `stock_cg_equity_mortgage_cninfo` | 未暴露 | vendor 有，建议补 wrapper |
| 风险核查 | 对外担保 | 相关数据较分散 | `stock_cg_guarantee_cninfo` | 未暴露 | AkShare 可补充 |
| 风险核查 | 商誉风险 | 可从报表或专题字段间接算 | `stock_sy_hy_em` 是行业级，不是公司级 | 未暴露 | 需要报表计算，vendor 只部分辅助 |
| 风险核查 | 关联交易 / 资金占用 | 多依赖公告文本 | 可通过公告索引拿到链接 | 未暴露 | 更适合 web/公告解析 |
| 事实查证 | 来源附录 / URL 追踪 | 公告接口可给 URL | 部分接口可给 URL | 当前无统一 source artifact | vendor 可覆盖部分，仍需 report/source 设计 |
| 通用研究 | 任意网页搜索 | 无 | 无 | 无 | 必须补 web/MCP |
| 通用研究 | 页面正文抽取 | 无 | 无 | 无 | 必须补 web/MCP |
| 通用研究 | HTML 表格抽取 | 无 | 无 | 无 | 必须补 web/MCP |


## 5. 按 prompt 维度拆解

### 5.1 可以优先走 vendor 的 prompt 字段

这部分最适合先做 `interface.py` 扩展：

- 最新价格、总市值、总股本、PB、股息率
- 三表和财务指标
- 主营业务构成
- 大股东 / 前十大股东
- 实控人 / 控制类型
- 回购
- 分红
- 管理层增减持
- 审计意见
- 公告索引

### 5.2 不适合只靠 vendor 的 prompt 字段

这部分即使 vendor 能提供部分线索，也不建议只靠结构化接口闭环：

- “为什么便宜”的叙事性归因
- “兑现路径是否真实存在”的多公告交叉验证
- “事件成功概率 >= 50%” 这种需要推断和证据分层的结论
- 来源附录、网页标题、抓取日期、用途
- 任意网页中的表格和正文抽取

### 5.3 最容易误判的地方

- `get_news` 不能等同于公司公告检索
- `get_insider_transactions` 这个名字偏美股语义，不适合直接承接 A 股“股东增减持 + 高管持股变动”
- `get_fundamentals` 当前返回的是摘要，不是 `cigbutt` 所需的多字段、多期、可计算底表


## 6. 当前仓库覆盖状态

### 6.1 已经有一定基础的部分

- `get_stock_data`
- `get_fundamentals`
- `get_balance_sheet`
- `get_cashflow`
- `get_income_statement`

说明：

- 这些方法足够支持“普通基本面摘要”
- 但还不够支持 `cigbutt` 的资产安全垫、股东结构、治理核查、回购/分红/公告链条

### 6.2 名义上有方法、实际上不适合直接用的部分

- `get_news`
  - A 股当前更接近“研报/资讯”，不是公告证据链
- `get_insider_transactions`
  - 当前 CN wrapper 基本未实现
  - A 股语义上更应该拆成“股东增减持”“高管持股变动”“实控人变化”

### 6.3 还没进入 `interface.py` 的关键能力

建议新增这类方法：

- `get_market_snapshot`
- `get_dividend_history`
- `get_shareholder_structure`
- `get_float_shareholder_structure`
- `get_controller_profile`
- `get_holder_trade_activity`
- `get_buyback_activity`
- `get_business_segments`
- `get_audit_opinion`
- `get_company_announcements`
- `get_equity_pledge`
- `get_corporate_guarantees`


## 7. 建议的 Phase 1 wrapper 清单

### 7.1 优先补 Tushare

优先原因：

- 结构化程度更高
- A 股财务与股东类字段更系统
- 更适合做统一 schema

建议优先补：

- `daily_basic`
- `top10_holders`
- `top10_floatholders`
- `stk_holdertrade`
- `repurchase`
- `dividend`
- `fina_mainbz`
- `fina_audit`
- `anns_d`
- `pledge_stat`
- `pledge_detail`

### 7.2 优先补 AkShare

优先原因：

- 巨潮资讯和东财接口更贴近公告、公司概况、控制关系、治理主题
- 可以弥补 `tushare` 在公告 URL、实控人、治理专题上的不足

建议优先补：

- `stock_value_em`
- `stock_profile_cninfo`
- `stock_zygc_em`
- `stock_zyjs_ths`
- `stock_hold_control_cninfo`
- `stock_ggcg_em`
- `stock_hold_management_detail_cninfo`
- `stock_zh_a_disclosure_report_cninfo`
- `stock_fhps_em`
- `stock_fhps_detail_em`
- `stock_cg_equity_mortgage_cninfo`
- `stock_cg_guarantee_cninfo`


## 8. 推荐实施顺序

### 8.1 路线 A: 先做结构化 `cigbutt` v1

适用场景：

- 先做 A 股烟蒂分析
- 优先让 agent 能算、能判定、能出结构化结论
- 暂时不追求完整网页 provenance

建议顺序：

1. 扩 `interface.py` 方法注册
2. 新增 Tushare / AkShare wrapper
3. 让 `cigbutt` analyst 优先消费结构化数据
4. 报告里把缺失网页来源字段标记为 `MISSING`

### 8.2 路线 B: 先做 web-first `cigbutt`

适用场景：

- 目标是贴近原 prompt
- 强调来源附录、URL、网页证据链
- 不满足于结构化 vendor 数据

建议顺序：

1. 新增 `web_search` / `fetch_page` / `extract_tables`
2. 再把 vendor data 当成辅助补充
3. 最后统一 `cigbutt_sources` 和 `cigbutt_artifact`

### 8.3 当前项目最稳妥的建议

对这个仓库，最稳妥的是：

- Phase 1 先补结构化 wrapper
- 把 `cigbutt` 做成 A 股优先、vendor-assisted 的 sidecar report
- Phase 2 再补 web/MCP 工具，升级到 prompt 原版的网页证据模式


## 9. 最小可行结论

一句话总结：

- `akshare` / `tushare` 文档里，已经有大量适合 `cigbutt` 的结构化接口
- 当前仓库并没有把这些能力充分接进 `interface.py`
- 真正缺的主要是 wrapper 和 tool 暴露，而不是 vendor 数据本身
- 但如果目标是“联网搜索 + 网页抓取 + 来源附录”的原始 prompt，vendor 仍然不能替代通用 web 工具


## 10. 官方文档索引

### 10.1 Tushare

- `daily_basic`: https://tushare.pro/document/2?doc_id=32
- `top10_holders`: https://tushare.pro/document/2?doc_id=61
- `top10_floatholders`: https://tushare.pro/document/2?doc_id=62
- `fina_mainbz`: https://tushare.pro/document/2?doc_id=81
- `fina_audit`: https://tushare.pro/document/2?doc_id=80
- `repurchase`: https://tushare.pro/document/2?doc_id=124
- `stk_holdertrade`: https://tushare.pro/document/2?doc_id=175
- `anns_d`: https://tushare.pro/document/2?doc_id=176

### 10.2 AkShare

- 股票数据总索引: https://akshare.akfamily.xyz/data/stock/stock.html
- 数据字典: https://akshare.akfamily.xyz/data/index.html
- 相关接口关键词:
  - `stock_value_em`
  - `stock_profile_cninfo`
  - `stock_zygc_em`
  - `stock_zyjs_ths`
  - `stock_hold_control_cninfo`
  - `stock_ggcg_em`
  - `stock_hold_management_detail_cninfo`
  - `stock_zh_a_disclosure_report_cninfo`
  - `stock_fhps_em`
  - `stock_fhps_detail_em`
  - `stock_cg_equity_mortgage_cninfo`
  - `stock_cg_guarantee_cninfo`
