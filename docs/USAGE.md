# 完整使用文档

> 本文档是 README 的"开发者手册"补充：包含所有启动命令、接口说明、Provider 配置细节、Amadeus OAuth2 接入步骤、字段映射原理等。

---

## 启动

```powershell
cd "D:\AI agent\Flowise-flowise-3.1.4\PythonProject\ticket-agent"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

打开：http://127.0.0.1:8010/docs

首次使用自然语言接口前，需要启动 Ollama，并确认 `.env` 中的模型已经下载：

```powershell
ollama serve
ollama pull qwen2.5:3b
```

如果你的 Ollama 使用了其他端口或模型，修改 `.env` 中的 `LLM_HOST` 和 `LLM_MODEL`。

---

## 第一阶段请求示例

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

后续再加入具体平台字段映射、Dijkstra 路线规划和 Yen K 条候选路径。

---

## 自然语言接口

请求 `POST /plan/text`：

```json
{
  "message": "9月20日早上8点以后从太原去北京，预算500元，优先高铁，不接受中转"
}
```

系统会先返回解析后的 `parsed_request`，信息完整时再返回 `options`；如果缺少出发地、目的地或日期，会在 `clarification` 中提示需要补充的字段。

---

## Agent 工具调用接口

第四阶段主接口是 `POST /agent/plan`，`POST /plan/text` 继续保留兼容。

当用户指定"优先高铁"时，Agent 会调用：

```text
search_train
```

当用户允许多种交通方式时，Agent 会并发调用对应工具。响应中的 `tool_calls` 会记录每个工具的名称、状态和返回结果数量。

响应中的 `agent_mode` 表示本次使用的方式：

```text
ollama-function-calling       原生工具调用
deterministic-fallback        模型不支持时的安全降级
```

---

## 多轮对话

`POST /agent/plan` 支持 `session_id`。第一次请求不完整时，响应会返回缺少的字段和会话 ID；下一次请求携带同一个 `session_id`，系统会合并上一次的出行条件。

使用 `DELETE /agent/session/{session_id}` 可以清空会话。当前会话存储在内存中，重启服务后会清空，后续可替换为 Redis 或数据库。

---

## Provider 可靠性和真实 API 接入

Provider 工厂会读取 `.env`：

- `TRAIN_PROVIDER_URL`、`FLIGHT_PROVIDER_URL`、`TAXI_PROVIDER_URL` 有值时，使用 HTTP JSON Provider；
- 没有配置时，继续使用 `data/mock` 中的本地演示数据；
- 请求超时会按照 `PROVIDER_MAX_RETRIES` 自动重试；
- 连续失败达到阈值后会暂时熔断，避免反复请求故障服务。

访问 `GET /providers/status` 可以查看每个 Provider 的模式、熔断状态、成功次数、失败次数和重试次数；中文网页中的"查看服务状态"按钮也会展示这些信息。

真实平台接入时，需要在 `app/providers/http_json.py` 或新的具体 Provider 中完成字段映射，并在 `.env` 配置对应地址和鉴权方式。

统一方案目前包含：价格、出发/到达时间、耗时、中转次数、余票数、座位类型、是否可预订和预订链接。

通用字段映射器位于 `app/providers/mapper.py`，默认兼容 `from/to`、`departAt/arriveAt`、`fare`、`remaining` 等常见字段；如果平台字段不同，可以在具体 Provider 中传入 `field_map` 和 `items_path`。

---

## Amadeus 航班真实 Provider 联调

本项目已经内置 `app/providers/amadeus.py`，调用 Amadeus Flight Offers Search：先通过 OAuth2 Client Credentials 获取访问令牌，再调用航班报价接口，并将返回结果转换为项目统一的 `TransportOption`。

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

4. 先访问 `http://127.0.0.1:8010/providers/status`，确认航班项的 `mode` 为 `amadeus-test`。然后在网页或 `POST /agent/plan` 中查询，例如：

```json
{
  "message": "查询2026年9月20日从太原到北京的航班，预算2000元"
}
```

当前适配器支持项目常用的中文城市，并支持直接输入三字母 IATA 机场代码，例如 `TYN` 到 `PEK`。如果 API 返回的航班结果为空，先更换未来日期或用机场代码重试；测试环境的结果不等同于生产环境的实时出票库存。