
这个版本适合作为 `create_cigbutt_analyst(llm)` 里的 system prompt，user message 只需要传 `{ticker}`、`{analysis_date}`、`{output_language}` 之类的上下文字段即可。它也和当前 analyst 节点的实现风格相容，因为现有 fundamentals analyst 本来就是在 node 内部组 prompt、`llm.bind_tools(tools)`、让 agent 自己调用工具再返回 report。: contentReference[oaicite: 2]{index=2}

第二部分，我建议的 cigbutt agent 接入方案不是“把 `cigbutt` 混进现有 core analysts”，而是新开一个独立槽位，比如 `sidecar_agents=["cigbutt"]`。这样现有 `selected_analysts` 仍只代表会进入主研究链的四个 analyst，cigbutt 作为 sidecar 只负责生成独立报告。当前图编排已经是按 analyst key 动态生成 node、Msg Clear、tool node，并按顺序串起来，所以在执行层把 `execution_agents = selected_analysts + sidecar_agents` 很自然；同时默认 `selected_analysts` 仍保持现状不变，意味着老调用路径完全不变。: contentReference[oaicite: 3]{index=3}

我建议的形态是这样。核心主链继续保留 `market / social / news / fundamentals -> Bull/Bear -> Research Manager -> Trader -> Risk -> Portfolio`，cigbutt 不改这条链的输入语义；它只是在 analyst 阶段多跑一个 sidecar node，产出 `cigbutt_report`、`cigbutt_artifact`、`cigbutt_sources`。当前 Bull、Bear、Research Manager、Trader 都只显式读取 `market_report / sentiment_report / news_report / fundamentals_report`，所以 phase 1 最小耦合的关键不是“让他们兼容 cigbutt”，而是“先完全不让他们知道 cigbutt 的存在”。: contentReference[oaicite: 4]{index=4}

这里最关键的设计点，是把 cigbutt 做成“独立 report、独立状态、独立工具链”，而不是复用 fundamentals。当前 `AgentState` 和初始 propagation 只初始化四份 analyst report，`trading_graph.py` 的状态记录也只序列化四份 analyst report，runner 和 CLI 的 section/title/file map 也都只覆盖四份 analyst report；所以要做真正独立的 `cigbutt_report`，这些地方要一起补，但不需要碰研究/交易 prompt。: contentReference[oaicite: 5]{index=5}

我建议新增这些状态键：
`cigbutt_report: str`
`cigbutt_artifact: dict | None`
`cigbutt_sources: list[dict]`
`cigbutt_status: str | None`（这个可选，主要给 UI/progress 用）

对应的代码面，至少会改这些文件。`tradingagents/agents/analysts/cigbutt_analyst.py` 放 agent 本体；`tradingagents/agents/__init__.py` 导出 `create_cigbutt_analyst`；`tradingagents/agents/utils/agent_states.py` 和 `tradingagents/graph/propagation.py` 加独立 state；`tradingagents/graph/conditional_logic.py` 加 `should_continue_cigbutt()`；`tradingagents/graph/trading_graph.py` 加 `tools_cigbutt` 和 state log；`tradingagents/graph/setup.py` 接入 sidecar agent 构图；`cli/models.py`、`cli/utils.py`、`cli/main.py`、`tradingagents/runner.py` 增加独立选择槽位、进度显示、报告 section 和落盘路径。现有 `agents/__init__.py` 现在只导出四个 analyst factory，所以这一步是必需的。: contentReference[oaicite: 6]{index=6}

工具链我建议完全独立，不复用 fundamentals 的 provider 路线。原因有两个。第一，你已经明确要求“数据提取和联网查询都由 agent 做，暂时不支持 data provider”。第二，现有 fundamentals tool node 暴露的是 `get_fundamentals / get_balance_sheet / get_cashflow / get_income_statement` 这组结构化工具，而 fundamentals analyst 代码里虽然还额外用了 `get_insider_transactions`，但这整个工具面依然偏 provider/结构化数据，不适合承载“网页发现 + 页面抓取 + 表格抽取 + URL provenance”这种 cigbutt_web_v 1 的需求。更干净的做法，是给 cigbutt 单独定义 provider-free web tools，比如 `web_search`、`fetch_page`、`extract_tables`、`extract_ownership`、`extract_corporate_actions`。: contentReference[oaicite: 7]{index=7}

模型选择上，我建议 cigbutt 不跟其他 analyst 一样默认走 `quick_thinking_llm`，而是给它单独走 `deep_thinking_llm`，或者至少支持一个 per-agent override。当前 `setup_graph()` 里四个 analyst 都是按 `quick_thinking_llm` 创建的，包括 fundamentals；但 cigbutt_web_v 1 是一个更重的网页检索、证据整合和结构化判断任务，给它单独更强的模型会更稳。: contentReference[oaicite: 8]{index=8}

“独立选择槽位”这件事，我建议不要只是给现有 analyst checkbox 多加一个值，而是分成两个槽位。第一个槽位保持原样，叫 `Analysts Team`，还是 `market/social/news/fundamentals`；第二个槽位新增成 `Supplemental Reports` 或 `Specialized Agents`，先只有一个选项：`Cigbutt Agent`。当前 CLI 里 analyst 选择来自 `AnalystType` enum 和 `ANALYST_ORDER` questionary checkbox，runner/CLI 的 report mapping 也都默认只跟着这四个 analyst 走；分槽位以后，语义最清楚，也避免别人误以为 cigbutt 会自动进入主研究链。: contentReference[oaicite: 9]{index=9}

图路由上，我建议分两种模式。若 `selected_analysts` 非空，那么执行顺序是 core analysts 先跑，再跑 sidecar cigbutt，然后进入 Bull Researcher。这样主链不变，cigbutt 只是额外生成一份报告。若 core analysts 为空，但 sidecar_agents 有值，比如用户只勾了 cigbutt，那么最后一个 sidecar 不应再接 Bull Researcher，而应直接接 `END` 或一个很轻的 `Standalone Report Finalizer`。因为当前 CLI MessageBuffer 和 runner progress tracker 都把 Research/Trader/Risk/Portfolio 这些固定团队默认标成 pending；如果不加这个 standalone 分支，用户只跑 cigbutt 时 UI 会表现得像流程没走完。: contentReference[oaicite: 10]{index=10}

所以，progress/UI 这一层也要一起做一个最小修正：当 `has_core_analysts=False` 时，不要初始化固定团队状态；或者至少让 stage builder 只渲染实际会执行的团队。现在 CLI 的 `MessageBuffer` 会固定加入 Research/Trading/Risk/Portfolio，runner 的 `AnalysisProgressTracker` 也会固定把这些 agent 设成 pending；这是当前实现里最容易让“独立 cigbutt 模式”看起来卡住的地方。: contentReference[oaicite: 11]{index=11}

报告输出方面，我建议 cigbutt 走完全独立的 section。也就是在 state、runner 和 CLI 里新增 `cigbutt_report`，标题用 `Cigbutt Analysis`，文件路径用 `1_analysts/cigbutt.md`；同时把 `json-cigbutt` 那段结构化 artifact 单独写成 `1_analysts/cigbutt_artifact.json`，sources 则写成 `1_analysts/cigbutt_sources.json`。当前 `SECTION_FILE_MAP` 只有 `fundamentals_report -> fundamentals.md` 这一条基本面槽位，CLI 也只会把四个 analyst report 拼进完整报告，所以这里必须显式扩出来。: contentReference[oaicite: 12]{index=12}

整体上，我会把 phase 1 的边界画得很清楚：`cigbutt_report` 只负责“生成与展示”，不参与主投资决策；主决策继续只吃老四份 analyst report。等你把 cigbutt 报告质量跑稳、web tools 路线稳定后，再考虑 phase 2：新增一个可选开关，把 `cigbutt_artifact` 摘要注入 Bull/Bear/Research Manager/Trader 的上下文。这一步现在故意不做，正是为了减少耦合。当前这些节点都只从四份既有 analyst report 组装 `curr_situation`。: contentReference[oaicite: 13]{index=13}

一句话总结实现路线：先做 `cigbutt_web_v1 + provider-free web tools + 独立 sidecar slot + 独立 cigbutt_report`，并支持“仅 cigbutt 单跑直接结束”；先不改 Bull/Bear/Research/Trader 的 prompt，不和 fundamentals 兼容，不复用 fundamentals_report。这样默认行为不变、现有主链不动、cigbutt 可以尽快上线。下一步最合适的是我直接把这套方案展开成逐文件 patch skeleton。
:: contentReference[oaicite: 14]{index=14}