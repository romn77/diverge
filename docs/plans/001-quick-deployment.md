# 单机 Docker 快速部署实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为当前 TradingAgents 项目提供一套贴合现状的单机部署方式，使用 Dockerfile 打包前后端运行环境，并通过 Docker Compose 在一台机器上稳定启动 Web 界面和后台分析任务。

**Architecture:** 当前项目的 Web 任务流依赖本地 `reports/` 目录、`reports/.tmp/` 临时写入、以及后端进程内的任务状态，因此最合适的部署方式是单机部署。采用“两容器 + 主机挂载目录”的方式：一个容器运行 FastAPI backend，一个容器运行 Next.js frontend，二者由 root 级 `docker-compose.yml` 编排，主机目录负责持久化报告和提供 `.env` 配置。

**Tech Stack:** Docker, Docker Compose, FastAPI, Uvicorn, Next.js, Node.js, Python 3.11+, root `.env`, host bind mounts

---

## 1. 结论与可行性

### 推荐结论

当前项目最适合先落地为：

- **单机部署**
- **Docker Compose 编排**
- **两个容器**
  - `backend`: `web/backend/main.py`
  - `frontend`: `web/frontend`
- **主机挂载**
  - `./reports` 持久化分析结果
  - `./.env` 供 backend 读取 provider key 可用性

### 可行性判断

**可行性：高。**

原因：

1. 当前前后端运行边界已经清晰
   - backend 是 FastAPI + Uvicorn
   - frontend 是 Next.js

2. 当前状态管理天然更适合单机
   - 任务状态保存在 backend 进程内存中
   - 任务执行使用后台线程
   - 报告产物直接写本地文件系统

3. Docker 正好能解决当前的主要痛点
   - Python / Node.js 环境打包
   - 启动方式统一
   - 依赖安装可复现
   - 主机只需要 Docker 和 Docker Compose

### 为什么现在不建议收敛到多机 / 云原生

以下设计都还没有抽离成分布式友好的形态：

- `web/backend/main.py` 中的内存 `tasks` 字典
- `reports/.tmp/<task_id>` 的本地临时写入
- 任务线程与 Web API 进程绑定
- 报告目录直接依赖本地文件系统

所以这份计划**明确只覆盖单机部署**，不处理：

- 多实例横向扩容
- 共享对象存储
- Redis / 数据库任务状态
- 独立 worker 队列
- 反向代理 / HTTPS / 域名治理

---

## 2. 单机目标拓扑

### 目标运行形态

在一台机器上运行以下组件：

1. **frontend 容器**
   - 监听 `3000`
   - 运行 `next start`
   - 提供 Web UI

2. **backend 容器**
   - 监听 `8000`
   - 运行 `uvicorn web.backend.main:app`
   - 提供 report API 和 task API

3. **主机目录**
   - `./reports`：分析结果持久化
   - `./.env`：LLM provider keys 和部署环境变量

### 数据流

1. 用户访问 frontend
2. frontend 调用 backend API
3. backend 在本地 `reports/.tmp` 写任务临时结果
4. 任务完成后，backend 将结果转正到 `reports/<REPORT_ID>/`

### 关键约束

- `reports` **必须读写挂载**，不能是只读
- backend 容器必须能看到项目根 `.env`
  - 当前 provider 可用性逻辑读取的是项目根 `.env`
- frontend 的 `NEXT_PUBLIC_API_BASE_URL` 是**构建时变量**
  - 修改后需要重新 build frontend 镜像
- 当前开发脚本 `web/start.sh` 中的 `3000` / `8000` 是写死的
  - 如果要在部署方案中支持可配置 frontend 端口，需要在 Docker Compose 和 CORS 配置层面显式处理

### 公网暴露策略

这个项目当前的前端实现会在浏览器中直接请求 `NEXT_PUBLIC_API_BASE_URL`，因此**是否只暴露一个公网入口**取决于是否额外引入代理层：

1. **当前计划的默认模式（无反向代理）**
   - 需要对外提供 **2 个可访问端口**
   - `3000`: frontend
   - `8000`: backend API
   - 原因：浏览器会直接请求 backend API，而不是通过 frontend 容器转发

2. **未来优化模式（有反向代理 / 单域名）**
   - 可以只对外提供 **1 个公网入口**
   - 例如 `80/443 -> reverse proxy -> frontend/backend`
   - 但这超出本计划范围

**本计划结论**:

- 单机 Docker 方案本身完全可行
- 在**不增加反向代理**的前提下，服务器层面应预期开放 **两个端口**
- 如果你强烈要求只开放一个公网入口，需要追加一层 Nginx / Caddy / Traefik 或 Next.js rewrite 代理方案
- frontend 的公网访问端口将通过环境变量 `FRONTEND_PORT` 控制

---

## 3. 推荐部署方案

### 推荐方案

使用：

- root 级 `docker-compose.yml`
- `web/backend/Dockerfile`
- `web/frontend/Dockerfile`
- root 级 `.dockerignore`
- 可选 `scripts/deploy-single-host.sh`

### 为什么不是单容器

不推荐把 frontend 和 backend 硬塞进一个镜像，原因：

- Python / Node.js 运行时耦合
- 镜像更重
- 构建缓存效果更差
- 前后端重建粒度更粗

### 为什么仍然推荐 Docker Compose

虽然是单机，但 Compose 仍然是最合适的原因：

- 启停简单
- 结构清晰
- 环境变量和挂载关系明确
- 比手写 `start.sh` 更适合“部署后常驻运行”

---

## 4. 文件布局决策

### 使用当前真实目录结构

这份计划必须遵守当前仓库结构：

```text
.
├── web/
│   ├── backend/
│   └── frontend/
├── tradingagents/
├── reports/
├── requirements.txt
├── pyproject.toml
└── .env
```

### 决策

1. backend 镜像
   - **Dockerfile 放在**: `web/backend/Dockerfile`
   - **build context 用仓库根目录**: `.`
   - 原因：backend 运行时需要导入 `tradingagents`、`cli`、`requirements.txt`、`pyproject.toml`

2. frontend 镜像
   - **Dockerfile 放在**: `web/frontend/Dockerfile`
   - **build context 用**: `./web/frontend`

3. Compose 文件
   - **放在仓库根目录**: `docker-compose.yml`

---

## 5. 实施任务

### Task 1: Backend 容器化

**Files:**
- Create: `web/backend/Dockerfile`
- Create: `.dockerignore`
- Verify: `web/backend/main.py`

**目标**

构建一个能直接运行 backend 的镜像，并且镜像在运行时拥有**整个仓库**作为上下文，而不是只包含一个孤立的 `web/backend` 子目录。

**实现要点**

1. `WORKDIR` 使用 `/app`
2. 复制 root 级依赖描述文件
   - `pyproject.toml`
   - `uv.lock`
   - `README.md`
   - `requirements.txt`
   - `web/backend/requirements.txt`
3. 安装 Python 依赖
   - 使用 `uv.lock` 作为锁文件来源
   - 使用 `uv sync --frozen --no-dev --extra web`
   - Python 基础镜像统一使用 `3.13`
4. 复制**整个仓库**
   - 采用 `COPY . .`
   - 通过 `.dockerignore` 排除 `reports/`、`.env`、`.venv`、前端构建产物等无关内容
5. 启动命令使用：
   - `uvicorn web.backend.main:app --host 0.0.0.0 --port 8000`

**关键注意**

- 不要把 `.env` bake 进镜像
- 不要把 `reports/` 打包进镜像
- backend 需要以**整个项目**作为打包上下文，否则后续如果引用根目录配置、脚本、模块或其他资源，会被镜像边界卡住
- backend Dockerfile 仍然放在 `web/backend/Dockerfile`，但 build context 必须是仓库根目录

**建议 Dockerfile 形态**

```dockerfile
FROM python:3.13-slim

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md requirements.txt ./
COPY web/backend/requirements.txt ./web/backend/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --extra web --no-install-project

COPY . .

RUN uv sync --frozen --no-dev --extra web

EXPOSE 8000

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**验证**

- `docker build -f web/backend/Dockerfile .`
- `curl http://localhost:8000/api/reports` 返回 200

---

### Task 2: Frontend 容器化

**Files:**
- Create: `web/frontend/Dockerfile`
- Verify: `web/frontend/package.json`

**目标**

构建一个 production 模式运行的 frontend 镜像。

**实现要点**

1. 使用 multi-stage build
2. 在 build 阶段执行：
   - `npm ci`
   - `npm run build`
3. 通过 `ARG NEXT_PUBLIC_API_BASE_URL` 注入后端地址
4. runtime 阶段执行：
   - `npm start`

**关键注意**

- `NEXT_PUBLIC_API_BASE_URL` 是 build-time 变量
- 如果部署到远程单机，不应写死为 `http://localhost:8000`，而应写成浏览器可访问的地址
- 本地开发型部署可用 `http://localhost:8000`
- 远程主机部署建议改成：
  - `http://<HOST_IP>:8000`
  - 或者未来引入反向代理后使用统一域名
- 这也意味着：如果当前阶段不做反向代理，backend 的 `8000` 端口必须允许浏览器访问
- frontend 的公网端口应由 `FRONTEND_PORT` 控制，而不是在 Compose 中写死 `3000`

**建议 Dockerfile 形态**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci

COPY web/frontend ./
RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts

EXPOSE 3000

CMD ["npm", "start"]
```

**验证**

- `docker build --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 -f web/frontend/Dockerfile web/frontend`
- `curl http://localhost:3000` 返回 200

---

### Task 3: Compose 编排

**Files:**
- Create: `docker-compose.yml`
- Modify: `web/backend/main.py`

**目标**

用一个命令启动完整单机服务，并支持通过环境变量调整 frontend 的对外端口。

**实现要点**

1. backend
   - build context: `.`
   - dockerfile: `web/backend/Dockerfile`
   - 端口映射: `8000:8000`
   - 目录挂载: `./reports:/app/reports`
   - 文件挂载: `./.env:/app/.env:ro`
   - 环境变量:
     - `FRONTEND_ORIGIN=${FRONTEND_ORIGIN}`
   - restart: `unless-stopped`

2. frontend
   - build context: `./web/frontend`
   - dockerfile: `Dockerfile`
    - build args:
      - `NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}`
   - 端口映射: `${FRONTEND_PORT:-3000}:3000`
   - depends_on: backend
   - restart: `unless-stopped`

3. backend CORS
   - 将 backend 当前写死的 `http://localhost:3000` 改为读取环境变量
   - 推荐变量名：`FRONTEND_ORIGIN`
   - 默认值可保留 `http://localhost:3000`

**端口策略说明**

- 如果按本计划默认模式运行，服务器需要允许访问：
  - `${FRONTEND_PORT}/tcp`
  - `8000/tcp`
- 如果后续加了反向代理，则可以把 backend 改成只在内网可达，并收敛为单入口

**关键注意**

- backend 对 `reports` 的挂载必须是 **读写**
- 不要再用历史计划里的 `:ro`
- backend 的 provider 可用性判断依赖项目根 `.env`，所以需要把 `.env` 挂进容器

**建议 compose 形态**

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: web/backend/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./reports:/app/reports
      - ./.env:/app/.env:ro
    environment:
      FRONTEND_ORIGIN: ${FRONTEND_ORIGIN}
    restart: unless-stopped

  frontend:
    build:
      context: ./web/frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
    ports:
      - "${FRONTEND_PORT:-3000}:3000"
    depends_on:
      - backend
    restart: unless-stopped
```

---

### Task 4: 部署配置与忽略规则

**Files:**
- Modify: `.env.example`
- Create: `.dockerignore`

**目标**

让部署配置最小可用，同时避免把无关文件打进镜像。

**`.env.example` 最少应包含**

```env
# Frontend public port on the host
FRONTEND_PORT=3000

# Browser-visible frontend origin used by backend CORS
FRONTEND_ORIGIN=http://localhost:3000

# Browser-visible backend URL used at frontend build time
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# LLM provider keys used by backend
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
XAI_API_KEY=
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
XIAOHUMINI_API_KEY=
```

**`.dockerignore` 最少应包含**

```text
.git
.venv
node_modules
web/frontend/.next
reports
.env
__pycache__
*.pyc
```

---

### Task 5: 单机部署脚本与文档

**Files:**
- Create: `scripts/deploy-single-host.sh`
- Modify: `README.md`
- Modify: `web/README.md`

**目标**

给操作者一个近似“一键部署”的入口。

**脚本职责**

1. 检查 Docker 和 Docker Compose
2. 检查 `.env` 是否存在
3. 确保 `reports/` 目录存在
4. 执行：
   - `docker compose build`
   - `docker compose up -d`
5. 输出访问地址和日志命令

**建议命令**

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

---

## 6. 验收标准

以下全部满足时，认为单机 Docker 部署可用：

1. 在仓库根目录执行 `docker compose up --build -d` 成功
2. `http://localhost:8000/api/reports` 返回 200
3. `http://localhost:${FRONTEND_PORT}` 可以打开前端页面
4. Web 中可以看到现有报告列表
5. Web 中发起新分析任务时，backend 能成功写入 `reports/.tmp/`
6. 任务完成后，报告能落在主机 `./reports/<REPORT_ID>/`
7. 重启容器后，已有报告仍然存在
8. 在远程单机部署时，浏览器能从 frontend 页面正常请求到 backend API
9. 修改 `FRONTEND_PORT` 后，重新部署可以在新端口访问 frontend

---

## 7. 风险与限制

1. **仅适合单机**
   - 任务状态仍在内存里
   - 不支持多实例共享任务进度

2. **frontend API 地址是构建时固定的**
   - 修改 `NEXT_PUBLIC_API_BASE_URL` 后需要重建 frontend 镜像

3. **本地磁盘是核心依赖**
   - `reports/` 丢失会导致历史报告丢失

4. **不包含 TLS / 域名 / 反向代理**
   - 本计划默认直接暴露 `3000` 与 `8000`
   - 这意味着当前阶段不是“单公网入口”方案

---

## 8. 明确不做

本计划不包含以下内容：

- Kubernetes
- Railway / Vercel / Cloud Run 多平台适配
- S3 / OSS / MinIO 持久化改造
- Redis / Postgres / Celery / RQ 任务队列化
- 多机部署
- 自动扩缩容

---

## 9. 推荐执行顺序

1. 先完成 `web/backend/Dockerfile`
2. 再完成 `web/frontend/Dockerfile`
3. 再补 root `docker-compose.yml`
4. 再补 `.dockerignore` 和 `.env.example`
5. 最后补 `scripts/deploy-single-host.sh` 与 README

---

## 10. 最终判断

**“单机 + Dockerfile + Docker Compose” 对当前项目是最合理、最贴合现状、也最容易真正落地的部署方案。**

它的优点不是“未来最强”，而是：

- 对现有架构改动最小
- 能直接打包环境
- 能在一台机器上稳定运行
- 能支撑当前的 Web 查看报告与发起任务能力

如果后续真的要走多机或云原生，应当在这个单机方案稳定后，再单独规划：

- 外部任务状态存储
- 共享报告存储
- 独立 worker
- 反向代理与统一域名
