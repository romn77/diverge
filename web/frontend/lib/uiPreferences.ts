export const THEME_VALUES = ["light", "dark", "proof", "everforest"] as const;
export type Theme = (typeof THEME_VALUES)[number];
export type Language = "en" | "zh";
export type VisualStyle = "normal" | "stylful";

export type TranslationParams = Record<string, number | string | undefined>;
export type TranslationTemplate =
  | string
  | ((params: TranslationParams) => string);

export const THEME_STORAGE_KEY = "diverge.ui.theme";
export const LANGUAGE_STORAGE_KEY = "diverge.ui.language";
export const VISUAL_STYLE_STORAGE_KEY = "diverge.ui.visualStyle";
export const THEME_COOKIE_NAME = THEME_STORAGE_KEY;
export const LANGUAGE_COOKIE_NAME = LANGUAGE_STORAGE_KEY;
export const VISUAL_STYLE_COOKIE_NAME = VISUAL_STYLE_STORAGE_KEY;
export const PREFERENCE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;
export const DEFAULT_THEME: Theme = "light";
export const DEFAULT_LANGUAGE: Language = "en";
export const DEFAULT_VISUAL_STYLE: VisualStyle = "normal";

export const LANGUAGE_LOCALES: Record<Language, string> = {
  en: "en-US",
  zh: "zh-CN",
};

const zhTranslations: Record<string, TranslationTemplate> = {
  "common.active": "当前",
  "common.cancel": "取消",
  "common.chinese": "中文",
  "common.clear": "清空",
  "common.close": "关闭",
  "common.dark": "深色",
  "common.everforest": "Everforest",
  "common.delete": "删除",
  "common.edit": "编辑",
  "common.english": "English",
  "common.interfacePreferences": "界面偏好",
  "common.language": "语言",
  "common.latest": "最新",
  "common.light": "浅色",
  "common.proof": "Proof",
  "common.loading": "加载中",
  "common.menu": "菜单",
  "common.normal": "标准",
  "common.notAvailable": "N/A",
  "common.notSet": "未设置",
  "common.open": "打开",
  "common.refresh": "刷新",
  "common.saved": "已保存",
  "common.settings": "设置",
  "common.stylful": "个性",
  "common.theme": "主题",
  "common.unknownDate": "未知日期",
  "common.updates": ({ count }) => `${count ?? 0} 条更新`,
  "common.view": "查看",
  "highlights.ariaLabel": "结构化报告亮点",
  "markdown.loadingContent": "正在加载报告内容",
  "markdown.scrollableTable": "可横向滚动的表格",
  "page.error.loadReports": "无法加载报告列表",
  "home.heroKicker": "Diverge 研究中心",
  "home.heroTitle": "以内容为中心的研究工作台",
  "home.heroDescription":
    "快速打开最新报告，按 ticker 搜索，发起新的后台分析，或构建排序后的选股池。",
  "home.openSidebar": "打开侧边栏",
  "home.searchLabel": "搜索报告",
  "home.searchPlaceholder": "按 ticker 或报告 ID 搜索",
  "home.searchHint": "可按 ticker、报告 ID 搜索，或使用下方快捷标签。",
  "home.launchAnalysis": "发起分析",
  "home.launchScreener": "发起筛选",
  "home.openManualJournal": "打开手动日志",
  "home.recentReports": "最近报告",
  "home.viewActivity": "查看活动",
  "home.analysisWorkspace": "分析工作台",
  "home.searchResultsTitle": ({ query }) => `${query ?? ""} 的分析结果`,
  "home.workspaceDescription":
    "搜索报告并继续已有覆盖。",
  "home.metric.reportLibrary": "报告库",
  "home.metric.reportLibraryMeta": "已索引报告总数",
  "home.metric.scopedReportLibraryMeta": "当前范围内报告",
  "home.metric.trackedTickersMeta": "报告库中的覆盖标的",
  "home.metric.activeResearch": "进行中研究",
  "home.metric.activeResearchMeta": "正在运行的分析任务",
  "home.searchPlaceholderShort": "Ticker 或报告 ID",
  "home.searchDeepLinkHint": "结果会即时更新，并把查询保留在 URL 中以便深链访问。",
  "home.matchingReports": "匹配报告",
  "home.matchingReportCount": ({ count }) => `${count ?? 0} 份匹配报告`,
  "home.jumpBack": "继续阅读覆盖标的",
  "home.loadingReportIndex": "正在加载报告索引...",
  "home.noReportMatches": "当前搜索还没有匹配报告。",
  "home.scope.label": "报告范围",
  "home.scope.all": "全部",
  "home.scope.mine": "我的",
  "home.scope.workspace": "工作区",
  "home.visibility.private": "私有",
  "home.visibility.workspace": "工作区",
  "home.coverageMap": "覆盖地图",
  "home.coverageSnapshot": "覆盖快照",
  "home.snapshotSearchFocus": "搜索正聚焦于报告库中的一个切片。",
  "home.snapshotHomeBase": "使用分析入口作为报告主工作区。",
  "home.snapshotSearchBody":
    ({ reports, tickers }) =>
      `当前查询正在过滤 ${reports ?? 0} 份已索引报告，覆盖 ${tickers ?? 0} 个 ticker。`,
  "home.snapshotLibraryBody":
    ({ reports, tickers }) =>
      `当前报告库包含 ${reports ?? 0} 份报告，覆盖 ${tickers ?? 0} 个 ticker；新的研究任务会通过统一侧边栏入口发起。`,
  "home.latestIndexedReport":
    ({ ticker }) => `最新索引报告 · ${ticker ?? ""}`,
  "home.reportsLatest": "最新",
  "home.reportsEmpty": "报告生成后会显示在这里。",
  "home.recentTickers": "最近 ticker",
  "home.waitingForReports": "等待报告中",
  "sidebar.reportNavigation": "报告导航",
  "sidebar.closeSidebar": "关闭侧边栏",
  "sidebar.launch": "发起",
  "sidebar.create": "新建",
  "sidebar.primaryNavigation": "主导航",
  "sidebar.workbenchNavigation": "工作台导航",
  "sidebar.section.research": "研究",
  "sidebar.section.portfolio": "组合",
  "sidebar.section.operations": "运营",
  "sidebar.nav.analysis": "分析",
  "sidebar.nav.screener": "筛选",
  "sidebar.nav.assets": "资产",
  "sidebar.nav.journal": "日志",
  "sidebar.nav.activity": "活动",
  "sidebar.meta.analysis": "报告与搜索",
  "sidebar.meta.screener": "运行与候选池",
  "sidebar.meta.assets": "台账与敞口",
  "sidebar.meta.journal": "交易复盘",
  "sidebar.noActiveWork": "没有进行中的后台任务",
  "sidebar.newAnalysisHint": "研究一个覆盖标的",
  "sidebar.newScreenerHint": "构建排序候选池",
  "sidebar.expand": "展开侧边栏",
  "sidebar.collapse": "收起侧边栏",
  "sidebar.newAnalysis": "新建分析",
  "sidebar.queueLocked": "当前任务未完成前，队列暂时锁定",
  "sidebar.screen": "筛选",
  "sidebar.newScreener": "新建筛选",
  "sidebar.manual": "手动",
  "sidebar.tradeJournal": "交易日志",
  "sidebar.taskQueue": "任务队列",
  "sidebar.screenerQueue": "筛选队列",
  "sidebar.activeCount": ({ count }) => `${count ?? 0} 项进行中`,
  "sidebar.screenerRun": "筛选任务",
  "sidebar.filterReports": "筛选报告",
  "sidebar.filterReportsPlaceholder": "Ticker 或报告 ID",
  "sidebar.filterReportsHint": "按 ticker 或报告 ID 过滤。",
  "sidebar.recentScreeners": "最近筛选",
  "sidebar.noScreenerRuns": "还没有筛选记录。",
  "sidebar.recentReports": "最近报告",
  "sidebar.shownCount": ({ count }) => `显示 ${count ?? 0} 条`,
  "sidebar.loadingReports": "正在加载报告...",
  "sidebar.noReports": "还没有报告。",
  "sidebar.allTickers": "全部 ticker",
  "sidebar.noTickerMatches": "当前筛选条件下没有匹配的 ticker。",
  "sidebar.viewLabel": "查看",
  "preferences.themeLabel": "界面主题",
  "preferences.languageLabel": "界面语言",
  "preferences.visualStyleLabel": "界面风格",
  "workspace.access": "工作台访问",
  "workspace.resetRequired": "需要重置",
  "workspace.adminConsole": "管理员控制台",
  "workspace.signingOut": "正在退出",
  "workspace.signOut": "退出登录",
  "workspace.syncing": "会话详情仍在同步中。",
  "workspace.openMode": "开放工作台",
  "workspace.openModeHint": "当前环境已禁用认证。",
  "sidebar.settingsLoadError": "无法加载侧边栏设置",
  "sidebar.retry": "重试",
  "sidebar.noOutputLanguages": "没有可用的输出语言。",
  "sidebar.outputLanguageHint": "新建分析表单会默认使用这个输出语言。",
  "workbench.sessionBootstrap": "会话初始化",
  "workbench.preparingTitle": "正在准备工作台",
  "workbench.preparingBody":
    "正在检查会话。",
  "workbench.unavailable": "工作台不可用",
  "workbench.authBoundaryTitle": "无法访问认证边界",
  "workbench.authBoundaryBody":
    "无法验证当前会话。",
  "workbench.retrySession": "重试会话初始化",
  "workbench.loginRequired": "需要登录",
  "workbench.loginRequiredTitle": "正在跳转到登录页",
  "workbench.loginRequiredBody":
    "请先登录后继续。",
  "report.generatedUnavailable": "生成时间不可用",
  "report.loadingReport": "正在加载报告...",
  "report.noReportData": "没有报告数据",
  "report.errorPrefix": "错误",
  "report.error.loadReport": "无法加载报告结构",
  "report.error.loadContent": "无法加载报告内容",
  "report.fileCount": ({ count }) => `该轨道包含 ${count ?? 0} 个文件`,
  "report.researchWorkbench": "研究工作台",
  "report.openNavigation": "打开报告导航",
  "report.overviewPanel": "报告概览",
  "report.collapseOverview": "收起概览",
  "report.expandOverview": "展开概览",
  "report.completeReport": "完整报告",
  "report.houseView": "综合观点",
  "report.pending": "等待中",
  "report.confidence": ({ value }) => `置信度 ${value ?? ""}`,
  "report.categoryView": ({ label }) => `${label ?? ""}视图`,
  "report.readingFile": ({ label }) => `正在阅读 ${label ?? ""}。`,
  "report.defaultRailHint": "使用分类栏在完整报告和各个 Agent 视图之间切换。",
  "report.currentFile": "当前文件",
  "report.filePerspective":
    ({ label, ticker }) =>
      `${label ?? ""} 展示了 ${ticker ?? ""} 在这一层面的观点。可单独阅读后，再与完整报告对照。`,
  "report.noCategoryData": "这个分类暂无数据",
  "report.category.analysts": "分析师",
  "report.category.research": "研究辩论",
  "report.category.trading": "交易计划",
  "report.category.risk": "风险评估",
  "report.category.portfolio": "组合决策",
  "report.file.market": "市场分析师",
  "report.file.sentiment": "社交情绪分析师",
  "report.file.news": "新闻分析师",
  "report.file.fundamentals": "基本面分析师",
  "report.file.bull": "看多研究员",
  "report.file.bear": "看空研究员",
  "report.file.manager": "研究经理",
  "report.file.trader": "交易员",
  "report.file.aggressive": "激进风险员",
  "report.file.conservative": "保守风险员",
  "report.file.neutral": "中性风险员",
  "report.file.decision": "组合决策",
  "analysis.dialog": "新建分析",
  "analysis.kicker": "发起分析",
  "analysis.title": "新建分析",
  "analysis.description": "选择 ticker 和参数后开始分析。",
  "analysis.loadingOptions": "正在加载分析配置...",
  "analysis.error.loadOptions": "无法加载分析配置项",
  "analysis.error.createTask": "无法创建分析任务",
  "analysis.ticker": "Ticker",
  "analysis.analysisDate": "分析日期",
  "analysis.analysts": "分析师",
  "analysis.researchDepth": "研究深度",
  "analysis.marketDataSource": "行情数据源",
  "analysis.marketDataSourceHint":
    "当 Yahoo Finance 限流时，美股价格历史可切换到 Massive。",
  "analysis.provider": "LLM 提供商",
  "analysis.providerHint":
    "只显示已配置 API Key 的供应商。",
  "analysis.outputLanguage": "输出语言",
  "analysis.reportVisibility": "报告可见性",
  "analysis.reportVisibilityHint":
    "私有报告仅自己可见；工作区公开报告会向同租户用户可见。",
  "analysis.visibility.private": "私有",
  "analysis.visibility.workspace": "工作区公开",
  "analysis.quickModel": "快速模型",
  "analysis.deepModel": "深度模型",
  "analysis.openaiReasoning": "OpenAI 推理强度",
  "analysis.googleThinking": "Google Thinking 等级",
  "analysis.providerUnavailable": "当前没有可用的 LLM 提供商，请先配置 API Key。",
  "analysis.pickAnalyst": "至少选择一位分析师后再发起任务。",
  "analysis.start": "开始分析",
  "analysis.starting": "正在发起...",
  "analysis.outputLanguage.en": "English (en)",
  "analysis.outputLanguage.cn": "简体中文 (cn)",
  "analysis.depth.1": "浅层",
  "analysis.depth.3": "中等",
  "analysis.depth.5": "深度",
  "analysis.depthDescription.1": "快速研究，辩论轮次较少",
  "analysis.depthDescription.3": "兼顾研究深度与策略讨论",
  "analysis.depthDescription.5": "更完整的辩论与风险讨论",
  "analysis.marketDataSource.yfinance": "Yahoo Finance",
  "analysis.marketDataSource.massive": "Massive",
  "analysis.provider.openai": "OpenAI",
  "analysis.provider.google": "Google",
  "analysis.provider.anthropic": "Anthropic",
  "analysis.provider.xai": "xAI",
  "analysis.provider.openrouter": "OpenRouter",
  "analysis.provider.deepseek": "DeepSeek",
  "analysis.provider.xiaohumini": "Xiaohumini",
  "analysis.analyst.market": "市场分析师",
  "analysis.analyst.sentiment": "社交情绪分析师",
  "analysis.analyst.news": "新闻分析师",
  "analysis.analyst.fundamentals": "基本面分析师",
  "analysis.reasoning.medium": "中等",
  "analysis.reasoning.high": "高",
  "analysis.reasoning.low": "低",
  "analysis.googleThinking.high": "启用 Thinking",
  "analysis.googleThinking.minimal": "最少 Thinking",
  "screener.dialog": "新建筛选",
  "screener.kicker": "发起筛选",
  "screener.title": "新建筛选",
  "screener.loadingOptions": "正在加载筛选配置...",
  "screener.error.loadOptions": "无法加载筛选配置项",
  "screener.error.createTask": "无法创建筛选任务",
  "screener.markets": "市场",
  "screener.marketHelp":
    "被禁用的后端市场通常需要服务端额外配置，例如 SCREEN_US_MANIFEST_PATH。",
  "screener.cnDataSource": "中国市场数据源",
  "screener.usDataSource": "美股数据源",
  "screener.asOfDate": "截至日期",
  "screener.topK": "Top K",
  "screener.selectMarket": "至少选择一个市场。",
  "screener.topKPositive": "Top K 必须为正数。",
  "screener.dateFormat": "as_of_date 必须使用 YYYY-MM-DD 格式。",
  "screener.start": "开始筛选",
  "screener.starting": "正在发起...",
  "screener.market.cn": "A 股 (cn)",
  "screener.market.us": "美股 (us)",
  "screener.cnSource.tushare": "Tushare",
  "screener.cnSource.akshare": "AkShare",
  "screener.usSource.yfinance": "Yahoo Finance",
  "screener.usSource.alpha_vantage": "Alpha Vantage",
  "screener.usSource.tushare": "Tushare",
  "screener.usSource.akshare": "AkShare",
  "screener.usSource.massive": "Massive",
  "screenerDashboard.title": "候选池工作台",
  "screenerDashboard.description":
    "发起筛选并查看候选池。",
  "screenerDashboard.newScreener": "新建筛选",
  "screenerDashboard.recentRuns": "最近运行",
  "screenerDashboard.recentRunsMeta": "已保存候选池",
  "screenerDashboard.activeBuilds": "进行中构建",
  "screenerDashboard.activeBuildsMeta": "后台筛选任务",
  "screenerDashboard.markets": "市场",
  "screenerDashboard.marketsMeta": "最近覆盖市场",
  "screenerDashboard.rankedPools": "排序候选池",
  "screenerDashboard.activeBuild": "进行中构建",
  "screenerDashboard.emptyRuns":
    "还没有筛选运行记录。发起一个新筛选来生成第一个排序候选池。",
  "screenerDashboard.runMeta":
    ({ markets, count }) => `${markets ?? ""} · ${count ?? 0} 个候选`,
  "screenerDashboard.previous": "上一期",
  "screenerDashboard.current": "当前",
  "screenerDashboard.metadataOnly": "仅元数据",
  "screenerDashboard.scope.mine": "我的",
  "screenerDashboard.scope.team": "团队",
  "screenerDashboard.staleResultTitle": "筛选条件已变更",
  "screenerDashboard.staleResultBody":
    "下方仍是上一轮结果。点击运行，用当前筛选条件生成新的候选池。",
  "screenerDashboard.staleResultDismiss": "隐藏上一轮结果",
  "screenerDashboard.resultSlot": "筛选结果",
  "screenerDashboard.placeholderReadyTitle": "等待运行",
  "screenerDashboard.placeholderReadyBody":
    "第一次运行完成后，排序候选会固定显示在这里。",
  "screenerDashboard.placeholderRunningTitle": "候选池构建中",
  "screenerDashboard.placeholderRunningBody":
    "当前筛选任务完成后，结果会自动显示在这里。",
  "screenerDashboard.placeholderOpenTask": "查看任务",
  "screenerDashboard.placeholderMarket": "市场",
  "screenerDashboard.placeholderFilters": "已选条件",
  "screenerDashboard.placeholderTopK": "Top K",
  "screenerDashboard.marketCoverage": "市场覆盖",
  "screenerDashboard.waitingHistory": "等待筛选历史",
  "screenerDashboard.queueSnapshot": "队列快照",
  "screenerDashboard.queueHint":
    "当前正在运行的筛选构建。进入活动页可按任务逐一监控。",
  "screenerDashboard.openActivity": "打开活动页",
  "activity.title": "后台任务",
  "activity.description":
    "集中查看分析和筛选任务。",
  "activity.metric.total": "进行中总数",
  "activity.metric.totalMeta": "合并后台任务",
  "activity.metric.analysis": "分析任务",
  "activity.metric.analysisMeta": "运行中的研究任务",
  "activity.metric.screener": "筛选任务",
  "activity.metric.screenerMeta": "运行中的候选池构建",
  "activity.analysisTasks": "分析任务",
  "activity.analysisDescription": "等待中或运行中的研究任务。",
  "activity.noAnalysisJobs": "没有进行中的分析任务。",
  "activity.failedAnalysisTasks": "失败的分析任务",
  "activity.failedAnalysisDescription": "失败或已取消的研究记录。",
  "activity.noFailedAnalysisJobs": "没有失败的分析任务。",
  "activity.screenerTasks": "筛选任务",
  "activity.screenerDescription": "当前正在运行的候选池构建。",
  "activity.noScreenerJobs": "没有进行中的筛选任务。",
  "activity.failedScreenerTasks": "失败的筛选任务",
  "activity.failedScreenerDescription": "失败或已取消的候选池记录。",
  "activity.noFailedScreenerJobs": "没有失败的筛选任务。",
  "activity.cancelTask": "取消任务",
  "activity.cancelTaskConfirm": "取消这个等待中的任务？运行中或已结束的任务不能取消。",
  "activity.deleteFailedTask": "删除失败任务",
  "activity.deleteFailedTaskConfirm":
    "删除这条失败任务记录？只会移除任务记录。",
  "activity.candidatePoolBuild": "候选池构建",
  "activity.awaitingUpdate": "等待下一次更新",
  "activity.awaitingWorker": "等待 worker 空位",
  "activity.waitingForQuota":
    ({ vendor, until }) =>
      `等待 ${vendor ?? "数据源"} 额度恢复${until ? `，预计 ${until}` : ""}`,
  "assets.title": "组合资产台账",
  "assets.description":
    "查看账户、持仓和资产敞口。",
  "assets.base": "基准",
  "assets.refreshDue": "刷新到期项",
  "assets.addAsset": "添加资产",
  "assets.editAsset": "编辑资产",
  "assets.createAsset": "创建资产",
  "assets.saveAsset": "保存资产",
  "assets.metric.marketValue": "市值",
  "assets.metric.marketValueMeta": "已定价持仓总额",
  "assets.metric.unrealized": "未实现盈亏",
  "assets.metric.unrealizedMeta": "所有已定价持仓",
  "assets.metric.positions": "持仓",
  "assets.metric.positionsMeta": "已跟踪资产",
  "assets.metric.accountsMeta": "组合账户",
  "assets.accounts": "账户",
  "assets.groupedExposure": "分组敞口",
  "assets.platformCount": ({ count }) => `${count ?? 0} 个平台`,
  "assets.loadingSummary": "正在加载资产摘要...",
  "assets.noGroups": "还没有已定价的平台分组。添加持仓或刷新手动估值。",
  "assets.accountCount": ({ count }) => `${count ?? 0} 个账户`,
  "assets.positionCount": ({ count }) => `${count ?? 0} 个持仓`,
  "assets.pnlValue": ({ value }) => `盈亏 ${value ?? ""}`,
  "assets.positionMeta":
    ({ quantity, category, state }) =>
      `数量 ${quantity ?? ""} · ${category ?? ""} · ${state ?? ""}`,
  "assets.ledgerHealth": "台账健康度",
  "assets.pricingState": "定价状态",
  "assets.priced": "已定价",
  "assets.unpriced": "未定价",
  "assets.forceRevalue": "强制重估全部持仓",
  "assets.unpricedQueue": "未定价队列",
  "assets.noUnpriced": "没有等待定价处理的未解决或仅手动估值持仓。",
  "assets.ledgerTable": "台账表",
  "assets.allPositions": "全部持仓",
  "assets.loadingLedger": "正在加载资产台账...",
  "assets.noPositions": "还没有跟踪持仓。",
  "assets.asset": "资产",
  "assets.account": "账户",
  "assets.quantityShort": "数量",
  "assets.state": "状态",
  "assets.value": "价值",
  "assets.actions": "操作",
  "assets.dialogDescription":
    "保存账户归属、持有数量，以及市场 ticker 或手动估值，让台账和组合经理保持一致。",
  "assets.platform": "平台",
  "assets.assetName": "资产名称",
  "assets.category": "类别",
  "assets.quantity": "数量",
  "assets.costBasis": "成本基础",
  "assets.currency": "货币",
  "assets.valuationMode": "估值模式",
  "assets.valuationMode.market": "市场",
  "assets.valuationMode.manual": "手动",
  "assets.ticker": "Ticker",
  "assets.manualPrice": "手动价格",
  "assets.notes": "备注",
  "assets.notesPlaceholder": "关于该持仓的可选内部备注。",
  "assets.error.loadLedger": "无法加载资产台账",
  "assets.error.loadSelected": "无法加载选中的资产",
  "assets.error.save": "无法保存资产",
  "assets.error.delete": "无法删除资产",
  "assets.error.refresh": "无法刷新资产",
  "assets.error.refreshLedger": "无法刷新资产台账",
  "assets.confirmDelete":
    ({ asset, platform, account }) =>
      `确认从 ${platform ?? ""} / ${account ?? ""} 删除 ${asset ?? ""}？`,
  "task.loading": "正在加载任务进度...",
  "task.error.loadTask": "无法加载任务",
  "task.kicker": "后台任务",
  "task.fallbackTitle": "新建分析",
  "task.requestDetails": ({ ticker }) => `${ticker ?? ""} 的请求详情`,
  "task.trackingDate":
    ({ date }) => `正在跟踪 ${date ?? ""} 这次研究流程，覆盖分析、辩论、交易和组合阶段。`,
  "task.trackingLive": "正在跟踪实时研究流程。",
  "task.viewReport": "查看报告",
  "task.cancel": "取消任务",
  "task.canceling": "正在取消...",
  "task.error.cancel": "无法取消任务",
  "task.currentAgent": "当前 Agent",
  "task.failedFallback": "分析任务失败。",
  "task.canceledFallback": "这个分析任务已取消。",
  "task.eventLog": "事件日志",
  "task.liveFeed": "实时进度流",
  "task.waitingUpdate": "正在等待第一条流式更新...",
  "task.status.pending": "待处理",
  "task.status.queued": "排队中",
  "task.status.waiting_for_quota": "等待额度",
  "task.status.running": "运行中",
  "task.status.completed": "已完成",
  "task.status.failed": "失败",
  "task.status.canceled": "已取消",
  "task.queuePosition": ({ position }) => `队列位置 ${position ?? ""}`,
  "task.queuedWaiting": "正在等待 worker 空位。",
  "task.waitingForQuota":
    ({ vendor, until }) =>
      `等待 ${vendor ?? "数据源"} 额度恢复${until ? `，预计 ${until}` : ""}。`,
  "task.stage.not_started": "未开始",
  "task.stage.processing": "处理中",
  "task.stage.completed": "已完成",
  "task.stage.Analysts": "分析师",
  "task.stage.Research": "研究辩论",
  "task.stage.Trading": "交易",
  "task.stage.Risk": "风险",
  "task.stage.Portfolio": "组合",
  "task.request.analysisDate": "分析日期",
  "task.request.provider": "LLM 提供商",
  "task.request.outputLanguage": "输出语言",
  "task.request.researchDepth": "研究深度",
  "task.request.quickModel": "快速模型",
  "task.request.deepModel": "深度模型",
  "task.depth.custom": "自定义",
  "screenerTask.kicker": "后台筛选任务",
  "screenerTask.title": "候选池构建",
  "screenerTask.viewResults": "查看结果",
  "screenerTask.cancel": "取消任务",
  "screenerTask.canceling": "正在取消...",
  "screenerTask.error.cancel": "无法取消筛选任务",
  "screenerTask.canceledFallback": "这个筛选任务已取消。",
  "screenerTask.progressLog": "进度日志",
  "screenerTask.noUpdates": "还没有进度更新。",
  "screenerTask.stage.Features": "特征",
  "screenerTask.stage.Filters": "过滤",
  "screenerTask.stage.Ranking": "排序",
  "screenerTask.stage.Export": "导出",
  "screenerResults.kicker": "筛选结果",
  "screenerResults.candidates": ({ count }) => `${count ?? 0} 个候选`,
  "screenerResults.column.rank": "排名",
  "screenerResults.column.total": "总分",
  "screenerResults.column.trend": "趋势",
  "screenerResults.column.momentum": "动量",
  "screenerResults.column.risk": "风险",
  "screenerResults.column.liquidity": "流动性",
  "screenerResults.header.symbol": "代码",
  "screenerResults.header.market": "市场",
  "screenerResults.header.global_rank": "总排名",
  "screenerResults.header.total_score": "总分",
  "screenerResults.header.trend_score": "趋势分",
  "screenerResults.header.momentum_score": "动量分",
  "screenerResults.header.risk_score": "风险分",
  "screenerResults.header.liquidity_score": "流动性分",
  "screenerResults.header.strategy_tags": "策略标签",
  "screenerResults.header.risk_flags": "风险标记",
  "screenerResults.empty": "暂无筛选候选结果。",
  "journal.title": "记录交易、区分入场和出场复盘，并预览未来的同 ticker 反馈",
  "journal.error.loadHistory": "无法加载交易历史",
  "journal.error.loadDetail": "无法加载交易详情",
  "journal.error.loadFeedback": "无法加载同 ticker 反馈",
  "journal.recordTrade": "记录交易",
  "journal.filterLabel": "按 Ticker 或 Trade ID 筛选",
  "journal.filterPlaceholder": "MSFT 或 trade_id",
  "journal.status": "状态",
  "journal.timeWindow": "时间范围",
  "journal.timeWindow.all": "全部",
  "journal.timeWindow.30d": "最近 30 天",
  "journal.timeWindow.90d": "最近 90 天",
  "journal.timeWindow.365d": "最近 12 个月",
  "journal.summary.totalRecords": "总记录数",
  "journal.summary.totalHint": "按后端 schema 保存的手动录入交易",
  "journal.summary.openStatus": "未平仓数量",
  "journal.summary.openHint": "仍在手动日志中标记为 open 的交易",
  "journal.summary.visible": "当前筛选可见",
  "journal.summary.visibleHint": "按 ticker、状态和活跃时间过滤后的历史记录",
  "journal.history": "历史记录",
  "journal.tradeRecords": "交易记录",
  "journal.loadingHistory": "正在加载手动交易历史...",
  "journal.noTradeMatch": "当前筛选条件下没有匹配的交易记录。",
  "journal.recordFirstTrade": "记录第一笔交易",
  "journal.entry": "入场",
  "journal.exit": "出场",
  "journal.entryPrice": "入场价",
  "journal.exitPrice": "出场价",
  "journal.loadingDetail": "正在加载交易记录和复盘详情...",
  "journal.selectTrade":
    "选择一条交易记录以查看字段、快照引用和复盘历史。",
  "journal.stableTradeId": "稳定 trade_id",
  "journal.editTrade": "编辑交易",
  "journal.marketExchange": "市场 / 交易所",
  "journal.plannedHorizon": "计划周期",
  "journal.size": "仓位",
  "journal.lastUpdated": "最近更新",
  "journal.stopLoss": "止损",
  "journal.takeProfit": "止盈",
  "journal.initialThesis": "初始交易逻辑",
  "journal.notes": "备注",
  "journal.noNotes": "暂无备注。",
  "journal.snapshotReferences": "关联快照引用",
  "journal.snapshotOnly": "仅绑定快照引用，不复制完整报告内容",
  "journal.linkedCount": ({ count }) => `已关联 ${count ?? 0} 条`,
  "journal.noSnapshots":
    "还没有附加分析快照。请先在交易记录中补充，再保存手动复盘。",
  "journal.tradeReviews": "交易复盘",
  "journal.distinguishReviews": "在同一个 trade_id 下区分 entry_review 与 exit_review",
  "journal.createReview": "创建复盘",
  "journal.editReview": "编辑复盘",
  "journal.entryReview": "入场复盘",
  "journal.exitReview": "出场复盘",
  "journal.reviewEmpty": "空",
  "journal.reviewSaved": "已保存",
  "journal.noReview":
    ({ reviewType }) =>
      `这笔交易还没有保存 ${reviewType ?? ""}。使用手动复盘编辑器补充后端 schema 需要的结构化字段。`,
  "journal.thesisAssessment": "逻辑评估",
  "journal.timingAssessment": "时点评估",
  "journal.sizingAssessment": "仓位评估",
  "journal.disciplineAssessment": "纪律评估",
  "journal.outcomeSummary": "结果总结",
  "journal.improvementActions": "改进行动",
  "journal.tickerSpecificLessons": "Ticker 专属经验",
  "journal.crossTickerTags": "跨 Ticker 标签",
  "journal.savedMeta":
    ({ date, updatedAt }) =>
      `分析日期 ${date ?? ""}，最近更新 ${updatedAt ?? ""}。`,
  "journal.sameTickerFeedback": "同 ticker 反馈",
  "journal.futureAnalyses": "后续分析会读取这里保存的复盘上下文",
  "journal.loadingFeedback": "正在加载同 ticker 反馈预览...",
  "journal.noFeedback":
    "该 ticker 还没有可复用的反馈提示。保存 entry_review 或 exit_review 后，后续分析即可复用。",
  "journal.promptPreview": "提示词预览",
  "journal.noneSaved": "未保存",
  "trade.side.long": "做多",
  "trade.side.short": "做空",
  "trade.status.open": "未平仓",
  "trade.status.closed": "已平仓",
  "tradeReview.manualOnly":
    "当前是纯手动 MVP：复盘聚焦于流程与快照引用，不代表自动交易或券商同步。",
  "tradeReview.manualReview": "手动复盘",
  "tradeReview.entryFocus": "聚焦入场时点的逻辑质量、时机、仓位和纪律。",
  "tradeReview.exitFocus": "结合原始逻辑、计划周期与实际风险管理来评估出场。",
  "tradeReview.linkSnapshotFirst":
    "保存复盘前，请先在交易记录中关联至少一条分析快照。",
  "tradeReview.snapshotContext": "快照上下文",
  "tradeReview.linkedSnapshots":
    ({ count }) => `正在使用 ${count ?? 0} 条关联快照`,
  "tradeReview.analysisDate": "分析日期",
  "tradeReview.error.save": "无法保存复盘",
  "tradeReview.noReferences":
    "这笔交易当前没有关联分析引用。请先编辑交易记录，确保复盘继续符合报告与 full-state-log 的约定。",
  "tradeReview.thesisPlaceholder":
    "这次交易逻辑是否明确、有证据支撑，并且适合当前 setup？",
  "tradeReview.timingPlaceholder":
    "结合当时的计划与已知信息，评价入场或出场时点是否合理。",
  "tradeReview.sizingPlaceholder":
    "仓位是否符合止损距离、风险预算和信念强度？",
  "tradeReview.disciplinePlaceholder":
    "执行过程是否遵守了既定规则和风险计划？",
  "tradeReview.outcomePlaceholder":
    "总结发生了什么，不要只用盈亏来下结论。",
  "tradeReview.actionsHelper": "每行写一条具体行动。",
  "tradeReview.actionsPlaceholder":
    "入场前先写清失效条件。\n加仓前确认催化剂质量。",
  "tradeReview.lessonsHelper": "只写适用于这个 ticker 或 setup 的经验。",
  "tradeReview.lessonsPlaceholder":
    "当云业务评论确认需求韧性时，MSFT 的 setup 往往更好。",
  "tradeReview.tagsHelper": "可选。每行一条，或用逗号分隔。",
  "tradeReview.tagsPlaceholder": "planned_stop\nquality_growth",
  "tradeReview.listItemRequired": "保存复盘前，至少添加一条列表项。",
  "tradeReview.save": ({ title }) => `保存${title ?? ""}`,
  "tradeRecord.manualJournal": "手动日志",
  "tradeRecord.recordTrade": "记录交易",
  "tradeRecord.editTrade": "编辑交易",
  "tradeRecord.createDescription": "为手动复盘补充一条手动录入的交易记录。",
  "tradeRecord.editDescription":
    "更新已保存的手动录入交易记录，不改变后端 schema。",
  "tradeRecord.marketExchange": "市场 / 交易所",
  "tradeRecord.side": "方向",
  "tradeRecord.status": "状态",
  "tradeRecord.entryTime": "入场时间",
  "tradeRecord.entryPrice": "入场价格",
  "tradeRecord.exitTime": "出场时间",
  "tradeRecord.exitPrice": "出场价格",
  "tradeRecord.size": "仓位",
  "tradeRecord.plannedHorizon": "计划周期",
  "tradeRecord.stopLoss": "止损",
  "tradeRecord.takeProfit": "止盈",
  "tradeRecord.initialThesis": "初始交易逻辑",
  "tradeRecord.initialThesisPlaceholder": "记录这笔交易存在的原因、催化因素和核心逻辑。",
  "tradeRecord.notes": "备注",
  "tradeRecord.notesPlaceholder": "执行备注、背景信息或后续跟进事项。",
  "tradeRecord.snapshots": "快照引用",
  "tradeRecord.bindSnapshots": "绑定分析快照，而不是复制完整报告",
  "tradeRecord.contractPrefix": "默认路径遵循 MAY-8 文件约定：",
  "tradeRecord.addBlankReference": "添加空白引用",
  "tradeRecord.quickAdd": "从报告快速添加",
  "tradeRecord.noQuickReports": "还没有可用于快速关联的报告。",
  "tradeRecord.noReferences":
    "还没有关联快照引用。交易记录仍可保存，但保存入场/出场复盘前，至少需要一条有效的报告和 full-state-log 引用。",
  "tradeRecord.snapshot": ({ index }) => `快照 ${index ?? 0}`,
  "tradeRecord.remove": "移除",
  "tradeRecord.reportPath": "报告路径",
  "tradeRecord.fullStateLogPath": "Full State Log 路径",
  "tradeRecord.error.save": "无法保存交易记录",
  "tradeRecord.create": "创建交易",
  "tradeRecord.saveChanges": "保存修改",
  "tradeRecord.saving": "保存中...",
};

export function isTheme(value: string | null | undefined): value is Theme {
  return THEME_VALUES.includes(value as Theme);
}

export function toColorScheme(theme: Theme): "light" | "dark" {
  return theme === "dark" || theme === "everforest" ? "dark" : "light";
}

export function isLanguage(value: string | null | undefined): value is Language {
  return value === "en" || value === "zh";
}

export function isVisualStyle(value: string | null | undefined): value is VisualStyle {
  return value === "normal" || value === "stylful";
}

export function toLocale(language: Language): string {
  return LANGUAGE_LOCALES[language];
}

export function toHtmlLang(language: Language): string {
  return language === "zh" ? "zh-CN" : "en";
}

export function resolveServerTheme(value: string | null | undefined): Theme {
  return isTheme(value) ? value : DEFAULT_THEME;
}

export function resolveServerVisualStyle(
  value: string | null | undefined
): VisualStyle {
  return isVisualStyle(value) ? value : DEFAULT_VISUAL_STYLE;
}

export function inferLanguageFromHeader(value: string | null | undefined): Language {
  if (!value) {
    return DEFAULT_LANGUAGE;
  }

  return /(^|,)\s*zh\b/i.test(value) ? "zh" : DEFAULT_LANGUAGE;
}

export function resolveServerLanguage(
  cookieValue: string | null | undefined,
  acceptLanguageHeader: string | null | undefined
): Language {
  return isLanguage(cookieValue)
    ? cookieValue
    : inferLanguageFromHeader(acceptLanguageHeader);
}

export function createPreferenceCookieString(name: string, value: string): string {
  return `${name}=${value}; path=/; max-age=${PREFERENCE_COOKIE_MAX_AGE_SECONDS}; samesite=lax`;
}

export function buildPreferencesBootstrapScript({
  initialLanguage,
  initialTheme,
  initialVisualStyle,
  preferSystemTheme,
}: {
  initialLanguage: Language;
  initialTheme: Theme;
  initialVisualStyle: VisualStyle;
  preferSystemTheme: boolean;
}): string {
  return `(() => {
  const root = document.documentElement;
  const storedTheme = (() => {
    try {
      const value = window.localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
      return ["light", "dark", "proof", "everforest"].includes(value) ? value : null;
    } catch (error) {
      return null;
    }
  })();
  const storedVisualStyle = (() => {
    try {
      const value = window.localStorage.getItem(${JSON.stringify(VISUAL_STYLE_STORAGE_KEY)});
      return value === "normal" || value === "stylful" ? value : null;
    } catch (error) {
      return null;
    }
  })();
  const nextTheme = storedTheme ?? (${preferSystemTheme}
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : ${JSON.stringify(initialTheme)});
  const nextLanguage = ${JSON.stringify(initialLanguage)};
  const nextVisualStyle = storedVisualStyle ?? ${JSON.stringify(initialVisualStyle)};
  root.dataset.theme = nextTheme;
  root.dataset.uiLanguage = nextLanguage;
  root.dataset.visualStyle = nextVisualStyle;
  root.lang = ${JSON.stringify(toHtmlLang(initialLanguage))};
  root.style.colorScheme = nextTheme === "dark" || nextTheme === "everforest" ? "dark" : "light";
  try {
    window.localStorage.setItem(${JSON.stringify(THEME_STORAGE_KEY)}, nextTheme);
    window.localStorage.setItem(${JSON.stringify(LANGUAGE_STORAGE_KEY)}, nextLanguage);
    window.localStorage.setItem(${JSON.stringify(VISUAL_STYLE_STORAGE_KEY)}, nextVisualStyle);
  } catch (error) {}
  document.cookie = ${JSON.stringify(
    createPreferenceCookieString(THEME_COOKIE_NAME, "")
  )}.replace("=", "=" + nextTheme);
  document.cookie = ${JSON.stringify(
    createPreferenceCookieString(LANGUAGE_COOKIE_NAME, initialLanguage)
  )};
  document.cookie = ${JSON.stringify(
    createPreferenceCookieString(VISUAL_STYLE_COOKIE_NAME, "")
  )}.replace("=", "=" + nextVisualStyle);
})();`;
}

export function translate(
  language: Language,
  key: string,
  fallback: TranslationTemplate,
  params: TranslationParams = {}
): string {
  const translation = language === "zh" ? zhTranslations[key] : undefined;
  const template = translation ?? fallback;
  return typeof template === "function" ? template(params) : template;
}

export function optionKey(value: string | number): string {
  return String(value).replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}
