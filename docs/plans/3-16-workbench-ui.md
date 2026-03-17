# Content-First Research Workbench — UI Redesign Plan

> 目标：把当前报告查看器改造成 "content-first 的研究工作台"，弱化装饰层，强化最近报告入口、阶段导航和长文阅读体验。
> Scope: page.tsx, globals.css, Sidebar.tsx, ReportViewer.tsx, HighlightCards.tsx, MarkdownContent.tsx
> Out of scope: 后端 API、报告生成逻辑、权限系统、深色模式、完整 i18n

---

## Phase 0 — 准备

- [ ] 跑一次 `node --test` 记录基线测试结果
- [ ] `npm run build` 确认当前可编译
- [ ] 截图当前 375px / 768px / 1280px 三档作为对照

---

## Phase 1 — globals.css 视觉基础层

### 1.1 收敛装饰层
- [ ] 删除 body 的 3 层 `radial-gradient` 和 `body::before` 白色渐变遮罩
- [ ] 删除 `.app-shell::after` 28px 网格线
- [ ] body background 改为纯 `var(--bg)`
- [ ] `.glass-panel` 去掉 `backdrop-filter: blur(16px)` 和 inset glow，降级为 `background: var(--surface); border: 1px solid var(--border); box-shadow: var(--shadow-soft)`
- [ ] `.card-surface:hover` 去掉 `translateY(-1px)` 上浮效果，保留细微 border-color 变化

### 1.2 三层 surface 定义
- [ ] `--surface-page`: `var(--bg)` — 页面底层
- [ ] `--surface-panel`: `var(--surface)` — 侧栏、header
- [ ] `--surface-elevated`: `var(--surface-strong)` + `box-shadow: var(--shadow-soft)` — 内容卡片
- [ ] 统一圆角：page 0, panel 12px, elevated 10px
- [ ] 主操作色保留橙色 `--primary`，信息色保留蓝色 `--accent`

### 1.3 阴影统一
- [ ] `--shadow-soft` 保留，作为 elevated 默认阴影
- [ ] `--shadow-hover` 简化为 `0 2px 8px rgba(15,23,42,0.08)`
- [ ] 删除 `--shadow-glow`（glass 效果废弃后不再需要）

---

## Phase 2 — globals.css 排版系统

### 2.1 字体栈
- [ ] `--font-body` 改为 `"Inter", "Noto Sans SC", "PingFang SC", system-ui, sans-serif`
- [ ] `--font-heading` 改为 `"Inter", "Noto Sans SC", "PingFang SC", system-ui, sans-serif`（同栈，靠 weight 区分）
- [ ] `--font-mono` 保留 `"JetBrains Mono", "SFMono-Regular", "Consolas", "Noto Sans Mono", monospace`

### 2.2 字号层级
- [ ] 定义 CSS 变量：
  ```
  --text-xs:  0.75rem;   /* 12px — 最小可用字号 */
  --text-sm:  0.875rem;  /* 14px */
  --text-base: 1rem;     /* 16px — 正文 */
  --text-lg:  1.25rem;   /* 20px */
  --text-xl:  1.75rem;   /* 28px */
  --text-2xl: 2.5rem;    /* 40px */
  ```
- [ ] 全局搜索替换所有 `text-[10px]`、`text-[11px]`、`font-size: 0.6rem`/`0.62rem`/`0.64rem`/`0.66rem`，最小提升到 `var(--text-xs)` (12px)
- [ ] 消灭所有微型全大写标签（`.terminal-chip-label` 等），改为 sentence case + `var(--text-xs)` + `font-weight: 600`

### 2.3 正文限宽与数字
- [ ] `.markdown-content` 加 `max-width: 74ch`
- [ ] 数据字段（chip value、table td、badge）加 `font-variant-numeric: tabular-nums`

---

## Phase 3 — page.tsx 启动面板

### 3.1 状态上提
- [ ] 把 `listReports()` 调用从 Sidebar 内部上提到 page.tsx
- [ ] page.tsx 新增 `reports` / `loading` / `error` state
- [ ] Sidebar 改为接收 `reports: Report[]` + `loading: boolean` + `error: string | null` 作为 props，删除内部 fetch 逻辑

### 3.2 启动面板 UI（selectedReportId === null 时）
- [ ] 顶部：内联搜索框（复用 Sidebar 搜索逻辑或共享 `searchQuery` state）
- [ ] 中部：最近 5 份报告列表，每条显示 ticker + date + time，点击直接 `onSelectReport`
- [ ] 底部：最近 ticker 快捷 chips（取 reports 前 5 个不重复 ticker）
- [ ] 删除当前 hero 大段说明文字和 3 个说明卡片

---

## Phase 4 — Sidebar.tsx 重构

### 4.1 导航信息架构
- [ ] 顶部新增 "Recent Reports" 区域，展示最近 3 条（跨 ticker）
- [ ] 下方保留 "All Tickers" 分组
- [ ] ticker 分组改为按最新报告时间排序（用 `parseReportTimestamp` 降序），而不是 `sort()` 字母序
- [ ] 每条 report 增加：生成时间显示优化、状态标签占位（signal badge placeholder）
- [ ] 展开/折叠图标从文字 `>` 改为 SVG chevron

### 4.2 交互和可访问性
- [ ] 搜索框增加可见 `<label>` 和 helper text "Filter by ticker or report ID"
- [ ] 保留 Clear 按钮
- [ ] 移动端：侧栏改为 `position: fixed` drawer + 半透明遮罩
- [ ] 新增 hamburger 按钮触发 drawer（放在 page.tsx 或 app shell 层）
- [ ] drawer 内加 focus trap（用原生 `<dialog>` 或手写 portal）
- [ ] 所有可点击元素 `min-height: 44px`

---

## Phase 5 — ReportViewer.tsx sticky header

### 5.1 header 压缩
- [ ] 主信息行：ticker（左）+ 生成时间 + final signal badge + report id（右），单行排列
- [ ] 删除当前 `grid-cols-[1fr_auto_1fr]` 三列布局和 "Trading Report" 装饰 badge
- [ ] header 改为 `position: sticky; top: 0; z-index: 10; background: var(--surface-panel)`

### 5.2 stage pills 改造
- [ ] 从 `flex-wrap` 改为 `overflow-x: auto; flex-wrap: nowrap; -webkit-overflow-scrolling: touch`
- [ ] 可横向滚动，隐藏滚动条（`scrollbar-width: none`）
- [ ] 激活态简化：去掉 gradient 和 glow shadow，改为 `background: var(--primary); color: white; border-color: var(--primary)`

### 5.3 二级 file tabs 分离
- [ ] 从 `<header>` 移到 `<section>` 内容区顶部
- [ ] 作为内容区的 sticky sub-header（`position: sticky; top: [header-height]`）
- [ ] 目标总高度：stage bar ≤ 56px + file bar ≤ 40px = 96px

---

## Phase 6 — HighlightCards.tsx 摘要导轨

### 6.1 从多层控制台 → 线性流
- [ ] 保留 hero verdict 区：signal badge + confidence + summary（去掉网格线/色条/渐变背景）
- [ ] hero 改为纯色背景 + 左侧 4px accent 色条
- [ ] 3 个 hero chips 保留为 key metrics 行
- [ ] console 双列 → 线性流：panels 按 `story → metrics/table → risk → actions` 依次排列
- [ ] 删除 `.terminal-console` 嵌套层，panels 直接平铺

### 6.2 CSS 精简
- [ ] 删除 `.terminal-hero::before`（网格线）和 `.terminal-hero::after`（色条用 border-left 替代）
- [ ] 删除 `.terminal-console::before`（顶部渐变线）
- [ ] 删除所有 `color-mix` 背景渐变，改为纯 CSS 变量色
- [ ] 目标：terminal-* CSS 从 ~530 行降到 ~150 行
- [ ] **不改 `highlightTerminal.ts`** — deck 数据结构仍然有用，只改渲染层

### 6.3 信号色彩保留
- [ ] `.signal-buy` / `.signal-hold` / `.signal-sell` 保留色彩语义
- [ ] 简化实现：去掉 `color-mix`，改为直接 CSS 变量

---

## Phase 7 — MarkdownContent.tsx 阅读模式

### 7.1 正文限宽
- [ ] `max-w-none` 改为 `max-w-[74ch]` + `mx-auto`

### 7.2 表格和代码块横向滚动
- [ ] 在 `ReactMarkdown` 的 `components` prop 中自定义 `table` 渲染器，外包 `<div class="overflow-x-auto">`
- [ ] `pre` 代码块已有 `overflow-x: auto`，确认移动端正常

### 7.3 标题 anchor 和层级间距
- [ ] 自定义 `h1`–`h4` 渲染器，添加 `id={slugify(text)}` anchor
- [ ] 增加标题上方间距（h2: `margin-top: 2em`, h3: `margin-top: 1.5em`）

### 7.4 loading 优化
- [ ] 删除当前全白覆盖 overlay（`bg-white absolute inset-0`）
- [ ] 改为顶部 2px progress bar（CSS animation `@keyframes progress-slide`）
- [ ] 初始加载（无内容）仍使用 skeleton

---

## Phase 8 — 响应式和语义修正

### 8.1 触控目标
- [ ] 所有可点击元素 `min-height: 44px`（Sidebar report items、tabs、chips）
- [ ] pill tabs padding 增加到 `py-2.5 px-4`

### 8.2 减少嵌套滚动
- [ ] 移动端：侧栏作为 drawer 独立滚动，主内容区独立滚动
- [ ] 桌面端：侧栏 `overflow-y: auto` + 主内容区 `overflow-y: auto`，页面本身不滚

### 8.3 tab 语义
- [ ] stage tabs 从 `role="tablist"` / `role="tab"` 改为 `<button>` 组 + `aria-pressed`
- [ ] 或补完整 roving tabindex（arrow key 导航 + Home/End）
- [ ] 决策：先用 `aria-pressed` button 组（更简单、更不易出错）

### 8.4 对比度修正
- [ ] `--muted` 从 `#64748b`（slate-500）提升到 `#475569`（slate-600），对比度 ≥ 7:1
- [ ] 检查所有 `text-slate-500` 使用处，决定是否统一替换

---

## Phase 9 — 验证

- [ ] 用真实长报告验证：`complete_report.md` 和 `trader.md`
- [ ] `node --test` 跑全部测试，修复因 CSS class 变更导致的正则断言
- [ ] `npm run build` 确认无编译错误
- [ ] 375px 走查：drawer 正常、无横向溢出、report 列表可用、阅读区限宽
- [ ] 768px 走查：侧栏 + 内容区并排、sticky header 正常、table 可横向滚动
- [ ] 1280px 走查：研究终端感、阅读区居中不过宽、highlights 摘要导轨清晰
- [ ] 确认移动端导航不阻塞内容访问

---

## 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 移动端优先目标 | 快速打开最新报告 | 移动端用户从通知/链接进入，侧栏浏览成本高 |
| HighlightCards 风格 | 简洁卡片（非 terminal） | terminal CSS 占 58% 代码量，维护成本高；简洁卡片更符合 content-first |
| UI 文案语言 | 英文 UI 骨架 + 报告内容跟随生成语言 | 领域术语中英文用户都能理解；i18n 后续 out of scope |
| tab 语义方案 | `aria-pressed` button 组 | 比完整 roving tabindex 简单，不易出错 |
| 移动端 drawer 实现 | 原生 `<dialog>` 或手写 portal | 不引入额外依赖，保持 6 个运行时包的轻量 |
| `highlightTerminal.ts` | 不改 | 数据结构仍然有用，只改 HighlightCards 渲染层 |

---

## 执行顺序

```
Phase 0 (准备)
  ↓
Phase 1 + 2 (globals.css 基础层 + 排版) — 骨架变更
  ↓
Phase 3 (page.tsx + state 上提) — 最大 prop 流变更
  ↓
Phase 4 (Sidebar 重构) — 依赖 Phase 3 的 props
  ↓
Phase 5 ‖ Phase 6 ‖ Phase 7 — 可并行的组件级重构
  ↓
Phase 8 (响应式 + 语义修正) — 全局收尾
  ↓
Phase 9 (验证走查)
```

Phase 5/6/7 互不依赖，可以并行执行。
