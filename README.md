# Ticket Agent · 多交通方式出行查询 Agent

基于 FastAPI、Ollama 和异步 Provider 的出行查询项目：将自然语言需求转为结构化条件，选择交通查询工具，再用确定性规则筛选结果。

默认使用本地 Mock 数据，另有通用 HTTP JSON Provider 和 Amadeus 航班适配器。目前不支持下单、支付或出票，不是生产订票平台。

## 招聘者快速浏览

- **解决的问题**：将自然语言出行需求转换为受校验的结构化条件，按交通类型调用查询工具，并用确定性规则筛选和排序候选方案。
- **工程实现**：Python + FastAPI + Pydantic + Ollama + asyncio；支持多 Provider 并发、超时/重试/熔断、会话补槽、工具白名单和服务状态观测。
- **可扩展性**：Mock、通用 HTTP JSON 与 Amadeus 航班适配器实现统一查询接口，并统一映射为 `TransportOption`，方便替换数据源。
- **可验证性与边界**：2026-10-09 本地运行 **11 项单元测试**通过。默认使用固定 Mock 演示数据；真实 API、模型解析准确率、订单与支付均不属于已完成能力。

### 架构概览

```mermaid
flowchart LR
    U[自然语言出行需求] --> P[Ollama 解析]
    P --> V[Pydantic 校验与会话字段合并]
    V -->|信息缺失| C[追问并暂存会话]
    V -->|信息完整| R[白名单工具路由 / 规则降级]
    R --> T[火车 / 航班 / 网约车查询工具]
    T --> M[Mock / HTTP JSON / Amadeus Provider]
    M --> Q[超时、重试与熔断]
    Q --> F[硬规则过滤与排序]
    F --> O[FastAPI JSON / 中文网页]
    O --> S[调用记录与 Provider 状态]
```

### 运行入口

```powershell
# 安装依赖并从 .env.example 创建 .env 后启动服务（完整步骤见“快速开始”）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

启动后访问 `http://127.0.0.1:8010/` 使用中文查询页面，或访问 `http://127.0.0.1:8010/api-docs` 查看 Swagger API 文档。

## 已实现的功能

| 能力 | 实现方式与边界 |
|---|---|
| 自然语言解析 | Ollama 提取地点、日期、预算等字段，Pydantic 校验类型，并对交通方式、中转指令作规则修正 |
| 缺失信息追问 | 不完整请求按 `session_id` 暂存字段，下一轮合并补充信息；不是完整对话历史管理 |
| 工具路由 | 优先使用 Ollama 原生 `tool_calls`，只执行白名单内且符合允许交通方式的工具；失败或没有有效调用时退回规则选择 |
| 多源并发与失败隔离 | `asyncio.gather(return_exceptions=True)` 查询火车、航班、网约车 Provider，单源异常以错误记录返回，保留其他源的结果 |
| Provider 抽象 | Mock、HTTP JSON、Amadeus 统一实现查询接口，映射为 `TransportOption`，由配置选择具体实现 |
| 硬规则过滤 | 检查可用状态、预算、最早出发时间、中转次数和时间顺序；按价格、耗时、中转次数排序 |
| 可靠性包装 | 每次尝试默认超时 8 秒、最多重试 2 次、指数退避；连续 3 次查询失败后简单熔断，冷却 30 秒 |
| Amadeus 适配 | OAuth2 Client Credentials 获取令牌，缓存并提前刷新，遇到 401 刷新后重试一次，映射 Flight Offers Search 返回值 |
| 可观测输出 | 中文网页、`tool_calls`、`provider_errors`、`agent_mode` 和 `/providers/status` 调用统计 |

价格、班次等结果字段从 Provider 返回值映射，不由 LLM 生成。但 Provider 可能是 Mock 或测试环境，解析也可能有误，不能据此声称“零幻觉”或真实可出票。

8 秒是单次 Provider 尝试的超时，不是整个请求的耗时上限。熔断和会话状态都保存在单进程内存中。

## 请求流程

```text
自然语言 → Ollama 解析 → Pydantic 校验与字段合并
                         ├─ 必填字段缺失 → 保存临时会话并追问
                         └─ 信息完整 → 白名单工具路由 / 规则降级
                                      → 并发执行 ReliableProvider
                                        （超时、重试、简单熔断包裹实际查询）
                                      → 统一字段 → 硬规则过滤与排序
                                      → JSON / 中文网页展示
```

工具执行使用已校验的 `TripRequest`，而不是直接采用模型生成的工具参数。结构化 `/plan` 可跳过 LLM，直接测试 Provider 查询与筛选。

## 快速开始

本地验证环境：Python 3.12.4。以下命令在项目根目录执行，依赖见 [requirements.txt](requirements.txt)。

### 1. 克隆、安装与配置

Windows PowerShell：

```powershell
git clone https://github.com/duanheming-afk/ticket-agent.git
cd ticket-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

已有 `.env` 时不要覆盖它。默认启用 Mock 查询，不需要第三方 API 凭据；`.env` 中的密钥不可提交到 Git。

Linux / macOS：

```bash
git clone https://github.com/duanheming-afk/ticket-agent.git
cd ticket-agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

以下 Windows 命令显式使用虚拟环境解释器；Linux / macOS 激活环境后将 `.\.venv\Scripts\python.exe` 换为 `python`。

### 2. 启动 API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

| 地址 / 接口 | 用途 |
|---|---|
| `http://127.0.0.1:8010/` 或 `/docs` | 中文查询网页 |
| `http://127.0.0.1:8010/api-docs` | Swagger API 文档 |
| `http://127.0.0.1:8010/api-redoc` | ReDoc API 文档 |
| `GET /health` | 基础进程状态，不检查外部服务是否可用 |
| `GET /providers/status` | Provider 模式、熔断状态与调用统计 |
| `POST /plan` | 结构化查询，不调用 LLM |
| `POST /agent/plan`、`POST /plan/text` | 自然语言 Agent 查询，两个入口使用同一处理流程 |
| `DELETE /agent/session/{session_id}` | 清空临时会话 |

### 3. 不使用 LLM 的 Mock 演示

在另一个 PowerShell 窗口执行：

```powershell
$demoRequest = @{
    origin = '太原'
    destination = '北京'
    travel_date = '2026-09-20'
    depart_after = '08:00'
    budget = 500
    transport_types = @('train')
    allow_transfer = $false
    max_transfers = 0
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8010/plan -Method Post -ContentType 'application/json; charset=utf-8' -Body $demoRequest
```

`2026-09-20` 是 Mock 数据的固定演示日期，不代表当前可购班次。换成其他日期可能返回空结果。结构化接口返回 `request`、`options`、`total`、`message` 和 `provider_errors`。

### 4. 使用自然语言查询

先安装并启动 Ollama，下载与 `.env` 中 `LLM_MODEL` 一致的模型：

```powershell
ollama pull qwen2.5:3b
```

如果 Ollama 尚未运行，在独立终端执行 `ollama serve`；已有后台服务时不必重复启动。当前 LLM 客户端只实现了 Ollama，尚未实现 OpenAI 兼容 API 客户端。

请求 `POST /agent/plan` 或 `POST /plan/text`：

```json
{
  "message": "查询2026年9月20日从太原到北京的火车，早上8点以后出发，预算500元，不接受中转",
  "session_id": null
}
```

返回 `parsed_request`、`options`、`tool_calls`、`provider_errors` 和 `agent_mode`；信息不完整时返回 `missing_fields`、`clarification`、`session_id`。下一轮带相同 `session_id` 补充字段。

工具路由支持规则降级，但意图解析仍依赖 Ollama；Ollama 不可用时，请使用结构化 `/plan` 演示接口。

## Provider 配置

模板见 [.env.example](.env.example)，操作说明见 [docs/USAGE.md](docs/USAGE.md)。

- 未配置外部地址时：使用 `data/mock`。
- 设置对应 `TRAIN_PROVIDER_URL`、`FLIGHT_PROVIDER_URL`、`TAXI_PROVIDER_URL` 时：使用 HTTP JSON Provider，需匹配外部平台字段和鉴权要求。
- 设置 `AMADEUS_ENABLED=true` 并填写凭据时：航班优先使用 Amadeus 适配器；默认地址是测试环境。
- 修改配置后需重启服务。测试环境报价不等于生产库存；适配器不执行预订或支付。

## 测试与验证范围

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

2026-10-09 本地核验：7 个测试文件、11 个测试全部通过。它们是单元测试，不是代码覆盖率报告。

| 测试文件 | 验证内容 |
|---|---|
| `test_parser.py` | Fake LLM 返回值的解析、交通方式与中转条件修正 |
| `test_rules.py` | 预算、出发时间、中转等硬规则筛选 |
| `test_tool_agent.py` | Fake Provider 的工具选择、执行与结果筛选 |
| `test_session.py` | 内存会话字段的保存、读取与清空 |
| `test_reliable_provider.py` | 失败后的重试恢复、达到阈值后熔断 |
| `test_mapper.py` | HTTP JSON 常见字段映射 |
| `test_amadeus.py` | 城市代码、时长解析及静态响应样例映射 |

上述测试无需 Amadeus 凭据，也没有调用真实外部 API。尚未提供真实模型解析准确率、OAuth2 在线联调、并发压测或覆盖率百分比报告。

## 代码导航

```text
app/main.py                 API 路由与服务组装
app/web.py                  中文网页
app/agent/                  意图解析、临时会话、工具路由
app/llm/ollama_client.py     Ollama 客户端
app/tools/                  工具注册表与交通查询工具
app/providers/              Mock / HTTP JSON / Amadeus、字段映射、可靠性包装
app/orchestration/service.py 结构化查询编排
app/validation/hard_rules.py 硬规则筛选与排序
app/schemas.py              请求与统一交通方案模型
tests/                      11 个单元测试
data/mock/                  固定演示数据
docs/USAGE.md               使用与接入说明
```

## 当前边界与后续方向

- 暂未实现跨交通方式中转组合规划；`app/planner/` 是占位目录，没有 Dijkstra / Yen 算法实现。
- 排序规则固定；`preference` 不是已实现的自定义偏好优化器。
- 会话只暂存不完整请求，没有完整历史、TTL、Redis 或数据库持久化；可靠性统计与熔断状态也不跨进程共享。
- 尚未提供用户鉴权、订单、支付和生产部署方案。
- 后续优先补充真实模型解析评测、外部 API 联调、故障注入与压测，再用可复现报告评价效果。

## 作者与许可

用于展示 AI Agent 应用开发与可靠性工程实践。

- GitHub：[@duanheming-afk](https://github.com/duanheming-afk)
- 许可：[MIT](LICENSE)
