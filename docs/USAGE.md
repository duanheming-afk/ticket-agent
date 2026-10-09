# 完整使用文档

> 本文档是 README 的"开发者手册"补充：包含所有启动命令、接口说明、Provider 配置细节、Amadeus OAuth2 接入步骤、字段映射原理等。

---

## 启动

先按 [README](../README.md) 创建虚拟环境、安装依赖，并从 `.env.example` 创建本地配置。以下命令在克隆后的 `ticket-agent` 项目根目录执行，不依赖作者电脑的绝对路径：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

中文网页：`http://127.0.0.1:8010/` 或 `/docs`；Swagger API 文档：`http://127.0.0.1:8010/api-docs`。

首次使用自然语言接口前，需要启动 Ollama，并确认 `.env` 中的模型已经下载。下载模型：

```powershell
ollama pull qwen2.5:3b
```

如果 Ollama 尚未运行，在独立终端执行 `ollama serve`；已有后台服务时不必重复启动。如果使用其他端口或模型，修改 `.env` 中的 `LLM_HOST` 和 `LLM_MODEL`。结构化 `/plan` 不依赖 LLM；自然语言意图解析仍依赖 Ollama，工具路由降级不能替代解析模型。

---

## 结构化查询示例

请求 `POST /plan`。以下日期匹配 `data/mock` 的固定演示数据，不代表当前可购班次；修改日期后可能返回空结果。

```json
{
  "origin": "太原",
  "destination": "北京",
  "travel_date": "2026-09-20",
  "depart_after": "08:00",
  "budget": 500,
  "transport_types": ["train", "flight", "taxi"],
  "allow_transfer": false,
  "max_transfers": 0,
  "preference": "优先高铁"
}
```

字段映射已实现；Dijkstra 路线规划和 Yen K 条候选路径尚未实现，`app/planner/` 当前是占位目录。结果按价格、耗时、中转次数排序，`preference` 不是自定义偏好优化器。

---

## 自然语言接口

请求 `POST /plan/text`：

```json
{
  "message": "查询2026年9月20日从太原到北京的火车，早上8点以后出发，预算500元，不接受中转"
}
```

系统会先返回解析后的 `parsed_request`，信息完整时再返回 `options`；如果缺少出发地、目的地或日期，会在 `clarification` 中提示需要补充的字段。

---

## Agent 工具调用接口

主接口是 `POST /agent/plan`，`POST /plan/text` 保留兼容，使用相同处理流程。

当解析后的允许交通方式仅为 `train` 时，白名单中可选择的工具是：

```text
search_train
```

当用户允许多种交通方式时，模型可以选择其中的工具；规则降级会选择所有符合允许类型的工具，并发执行。实际调用使用已校验的 `TripRequest`，不直接采用模型生成的参数。响应中的 `tool_calls` 记录工具名称、状态和返回结果数量，`provider_errors` 保留失败原因。

响应中的 `agent_mode` 表示本次使用的方式：

```text
ollama-function-calling       原生工具调用
deterministic-fallback        模型不支持时的安全降级
```

---

## 多轮对话

`POST /agent/plan` 支持 `session_id`。第一次请求不完整时，响应会返回缺少的字段和会话 ID；下一次请求携带同一个 `session_id`，系统会合并上一次的出行条件。

使用 `DELETE /agent/session/{session_id}` 可以清空会话。当前只保存不完整请求的字段，没有完整历史或已完成查询的持续记忆；会话存储在单进程内存中，没有 TTL，重启后会清空。Redis 或数据库持久化属于后续功能。

---

## Provider 可靠性和真实 API 接入

Provider 工厂会读取 `.env`：

- `TRAIN_PROVIDER_URL`、`FLIGHT_PROVIDER_URL`、`TAXI_PROVIDER_URL` 有值时，使用 HTTP JSON Provider；
- 没有配置时，继续使用 `data/mock` 中的本地演示数据；
- 航班配置 `AMADEUS_ENABLED=true` 时，优先使用 Amadeus，需要填写凭据；
- 每次尝试默认超时 8 秒，最多重试 2 次，退避间隔为 0.2、0.4 秒；这不是整个请求的 8 秒耗时上限；
- 连续 3 次查询耗尽重试仍失败后简单熔断，冷却 30 秒后允许重新查询；状态不跨进程共享。

访问 `GET /providers/status` 可以查看每个 Provider 的模式、熔断状态、成功次数、失败次数和重试次数；中文网页中的"查看服务状态"按钮也会展示这些信息。`GET /health` 仅返回基础进程状态，不探测外部服务就绪性。

真实平台接入时，需要在 `app/providers/http_json.py` 或新的具体 Provider 中完成字段映射，并在 `.env` 配置对应地址和鉴权方式。

统一方案目前包含：价格、出发/到达时间、耗时、中转次数、余票数、座位类型、是否可预订和预订链接。

通用字段映射器位于 `app/providers/mapper.py`，默认兼容 `from/to`、`departAt/arriveAt`、`fare`、`remaining` 等常见字段；如果平台字段不同，可以在具体 Provider 中传入 `field_map` 和 `items_path`。

---

## Amadeus 航班适配器与可选在线联调

本项目已经内置 `app/providers/amadeus.py`，调用 Amadeus Flight Offers Search：先通过 OAuth2 Client Credentials 获取访问令牌，再调用航班报价接口，并将返回结果转换为项目统一的 `TransportOption`。

适配器缓存访问令牌、提前刷新，并在遇到 401 时刷新后重试一次。现有 `test_amadeus.py` 仅验证辅助函数与静态响应映射，不调用外部 API；测试通过不表示 OAuth2 或在线查询已联调成功。

官方资料：

- 开发者快速开始与 OAuth2：<https://admin.developers.amadeus.com/self-service/apis-docs/guides/developer-guides/quick-start/>
- REST API 教程（含 Flight Offers Search）：<https://admin.developers.amadeus.com/self-service/apis-docs/guides/developer-guides/resources/>
- 自助开发者注册入口：<https://admin.developers.amadeus.com/self-service>

Amadeus 的测试环境使用 `https://test.api.amadeus.com`。官方流程是注册开发者账号、创建 App，然后在 App 页面取得 API Key 和 API Secret；这两个值是你的私有凭据，不能提交到 Git，也不要发给别人。

1. 复制环境变量文件：

```powershell
Copy-Item .env.example .env
```

2. 编辑 `.env`，填写自己的凭据：

```dotenv
AMADEUS_ENABLED=true
AMADEUS_BASE_URL=https://test.api.amadeus.com
AMADEUS_CLIENT_ID=这里填写你的API_Key
AMADEUS_CLIENT_SECRET=这里填写你的API_Secret
```

3. 重启 API 服务（项目使用 `reload=False`，只保存文件不会自动重新加载配置）：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

4. 先访问 `http://127.0.0.1:8010/providers/status`，确认航班项的 `mode` 为 `amadeus-test`。这只能确认选中了适配器；还需要实际请求才能验证凭据和网络。在线查询使用未来日期，不能沿用 Mock 的固定历史日期。例如在 PowerShell 动态生成两周后的日期：

```powershell
$flightMessage = '查询{0}从TYN到PEK的航班，预算2000元' -f (Get-Date).AddDays(14).ToString('yyyy-MM-dd')
$flightRequest = @{ message = $flightMessage } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8010/agent/plan -Method Post -ContentType 'application/json; charset=utf-8' -Body $flightRequest
```

当前适配器支持项目常用的中文城市，并支持直接输入三字母 IATA 机场代码，例如 `TYN` 到 `PEK`。如果 API 返回的航班结果为空，先更换未来日期或用机场代码重试；测试环境的结果不等同于生产环境的实时出票库存。

项目只查询和筛选结果，不执行下单、支付或出票。完整功能边界与测试范围见 [README](../README.md)。
