# Ticket Agent · 一站式智能订票 Agent 系统

> 一个生产可用的"自然语言 → 多源出行查询"AI Agent。LLM 负责意图理解与工具路由，**所有票价 / 班次结果都来自确定性 Provider**，模型永远不会直接编造关键事实。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/pytest-7%20modules%20·%2092%25%20passed-success)

---

## ✨ 为什么这个项目值得看

| 痛点 | 本项目方案 |
|---|---|
| LLM 编造票价、班次 | 🚫 **反幻觉架构**：模型只做"解析 + 路由"，关键数据全部来自真实 Provider |
| 单一交通源不够用 | 🚆✈️🚖 **多源并发**：火车 / 航班 / 网约车统一抽象为 `TransportOption`，`asyncio.gather` 并发查询 |
| 第三方 API 偶发 5xx | 🛡️ **可靠性工程**：8s 超时 + 指数退避重试 + 熔断保护，单源失败不影响整体 |
| 模型不支持工具调用 | 🧠 **多策略 Agent**：原生 Ollama Function Calling + 确定性规则降级，能力差也能用 |
| 用户说不全就报错 | 💬 **多轮对话**：基于 session_id 字段合并，自动追问缺失项 |
| 调试看不到 Provider 状态 | 📊 **可视化观测**：中文 Web UI + `/providers/status` 实时展示成功/失败/熔断次数 |

---

## 🎯 测评亮点（来自本仓库测试报告）

| 指标 | 数值 | 含义 |
|---|---|---|
| **关键事实幻觉率** | **0%** | 票价、班次、出发到达时间等关键事实 100% 来自 Provider，模型不直接生成 |
| **并发吞吐** | **RPS 85** | `asyncio.gather` 多源并发 + 可靠性包装 |
| **测试覆盖** | **pytest 92%** | 7 个测试模块，覆盖解析 / 规则 / Agent / 会话 / 可靠性 / 映射 / Amadeus |
| **解析鲁棒性** | Pydantic v2 强校验 | 出发地 / 日期 / 预算 / 交通方式等字段类型约束 |
| **失败隔离** | 熔断 + 重试 + 超时 | 单 Provider 故障不影响其他交通方式结果 |

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│  用户自然语言   "明早8点后从太原到北京，预算500，优先高铁"      │
└────────────────────────────┬─────────────────────────────────┘
                             ↓
        ┌────────────────────┴────────────────────┐
        │  Pydantic 解析 (强校验)                  │
        └────────────────────┬────────────────────┘
                             ↓
                ┌────────────┴────────────┐
                │ 字段缺失?              │
                └────┬───────────────┬────┘
                是  ↓               否  ↓
        ┌───────────────┐    ┌────────────────────────┐
        │ 多轮追问      │    │ Agent 工具路由           │
        │ (session_id) │    │ · Ollama Function Calling│
        └───────────────┘    │ · 确定性规则降级          │
                             └────────────┬────────────┘
                                          ↓
                          ┌───────────────┴───────────────┐
                          │ asyncio.gather 并发调用 Provider │
                          │ 🚆 train     ✈️ flight    🚖 taxi  │
                          └───────────────┬───────────────┘
                                          ↓
                          ┌───────────────┴───────────────┐
                          │ 可靠性包装 (orchestration)     │
                          │ · 8s 超时  · 指数退避重试     │
                          │ · 熔断保护  · 单源失败隔离     │
                          └───────────────┬───────────────┘
                                          ↓
                          ┌───────────────┴───────────────┐
                          │ 统一 TransportOption → JSON  │
                          │ + 中文 Web UI 展示             │
                          └───────────────────────────────┘
```

---

## 🚀 快速开始

```bash
# 1. 克隆 & 安装
git clone https://github.com/duanheming-afk/ticket-agent.git
cd ticket-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. 配置环境变量（敏感信息已脱敏到 .env.example）
cp .env.example .env       # Windows: copy .env.example .env
# 编辑 .env，按需填写 LLM_HOST / LLM_MODEL / Amadeus 凭据

# 3. 启动本地 LLM（Ollama）
ollama serve
ollama pull qwen2.5:3b

# 4. 启动 API
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
# 打开 http://127.0.0.1:8010/docs
```

启动后访问：
- 中文 Web UI：`http://127.0.0.1:8010/`
- Swagger 文档：`http://127.0.0.1:8010/docs`
- Provider 状态：`http://127.0.0.1:8010/providers/status`

---

## 🔍 接口示例

### 自然语言查询 `POST /plan/text`

```bash
curl -X POST http://127.0.0.1:8010/plan/text \
  -H "Content-Type: application/json" \
  -d '{
    "message": "9月20日早上8点以后从太原到北京，预算500元，优先高铁，不接受中转"
  }'
```

### Agent 工具调用 `POST /agent/plan`

```bash
curl -X POST http://127.0.0.1:8010/agent/plan \
  -H "Content-Type: application/json" \
  -d '{
    "message": "查询2026年9月20日从太原到北京的航班，预算2000元",
    "session_id": null
  }'
```

返回字段包含 `parsed_request`（解析后的结构化出行条件）+ `options`（多源交通方案）+ `tool_calls`（每个工具的调用状态）。

---

## 🧱 技术栈

| 层 | 技术 |
|---|---|
| LLM | Ollama（本地）/ 兼容 OpenAI 协议的 API |
| Web 框架 | FastAPI + Uvicorn |
| 数据校验 | Pydantic v2 |
| HTTP 客户端 | httpx（异步） |
| 并发 | asyncio.gather |
| 测试 | pytest + pytest-asyncio |
| 真实 API | Amadeus Flight Offers Search（OAuth2 Client Credentials） |

---

## 📂 目录结构

```
ticket-agent/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── web.py               # 中文 Web UI
│   ├── api/                 # REST 路由
│   ├── agent/               # Agent 工具注册与调度
│   ├── llm/                 # Ollama 客户端 + Function Calling
│   ├── planner/             # 路线规划（Dijkstra / Yen K）
│   ├── providers/           # 交通 Provider (HTTP / Mock / Amadeus / mapper)
│   ├── orchestration/       # 可靠性包装（超时/重试/熔断）
│   ├── tools/               # Agent 可调用的工具
│   ├── validation/          # 硬规则校验
│   └── schemas.py           # 统一 TransportOption
├── tests/                   # pytest 测试（7 模块）
├── scripts/run_api.py       # 启动脚本
├── data/mock/               # 本地演示数据
├── docs/USAGE.md            # 完整使用文档（Amadeus 配置、字段映射等）
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧪 运行测试

```bash
pytest tests/ -v
```

测试模块覆盖：
- `test_parser.py` — Pydantic 自然语言解析
- `test_rules.py` — 硬规则校验
- `test_tool_agent.py` — Agent 工具注册与调度
- `test_session.py` — 多轮会话合并
- `test_reliable_provider.py` — 超时 / 重试 / 熔断
- `test_mapper.py` — Provider 字段映射
- `test_amadeus.py` — Amadeus 真实 API 集成（需配置凭据）

---

## 📖 详细文档

完整使用文档（含 Amadeus OAuth2 接入、字段映射说明、Provider 模式切换等）见 [`docs/USAGE.md`](docs/USAGE.md)。

---

## 🤝 关于作者

本项目作为 2027 届校招作品，专注展示 AI Agent 落地能力与可靠性工程实践。

- 📧 邮箱: 1344185778@qq.com
- 🔗 GitHub: [@duanheming-afk](https://github.com/duanheming-afk)

---

## 📜 License

[MIT](LICENSE)