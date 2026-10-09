"""中文订票网页。"""

from fastapi.responses import HTMLResponse


def home_page() -> HTMLResponse:
    return HTMLResponse(
        content="""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>一站式智能订票 Agent</title>
  <style>
    :root { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: #172033; background: #f4f7fb; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; }
    .page { max-width: 1080px; margin: 0 auto; padding: 42px 20px 64px; }
    .hero { color: white; background: linear-gradient(135deg, #2563eb, #0f766e); border-radius: 24px; padding: 34px; box-shadow: 0 18px 45px rgba(37, 99, 235, .18); }
    h1 { margin: 0 0 10px; font-size: 30px; }
    .subtitle { margin: 0; color: #dbeafe; line-height: 1.7; }
    .panel { margin-top: 22px; background: white; border-radius: 18px; padding: 24px; box-shadow: 0 8px 24px rgba(15, 23, 42, .07); }
    label { display: block; margin-bottom: 10px; font-weight: 700; }
    textarea { width: 100%; min-height: 120px; resize: vertical; border: 1px solid #cbd5e1; border-radius: 12px; padding: 14px; font: inherit; line-height: 1.6; outline: none; }
    textarea:focus { border-color: #2563eb; box-shadow: 0 0 0 3px #dbeafe; }
    .actions { display: flex; gap: 12px; align-items: center; margin-top: 14px; flex-wrap: wrap; }
    button, .link-button { border: 0; border-radius: 10px; padding: 11px 18px; font: inherit; cursor: pointer; text-decoration: none; }
    button { color: white; background: #2563eb; font-weight: 700; }
    button:disabled { opacity: .6; cursor: wait; }
    .link-button { color: #1d4ed8; background: #eff6ff; }
    .hint { color: #64748b; font-size: 14px; }
    .example { color: #1d4ed8; cursor: pointer; }
    .hidden { display: none; }
    .status { margin-top: 18px; padding: 12px 14px; border-radius: 10px; background: #eff6ff; color: #1e40af; }
    .error { background: #fef2f2; color: #b91c1c; }
    .section-title { margin: 0 0 14px; font-size: 19px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }
    .info-card, .option { border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px; background: #fbfdff; }
    .info-card strong { display: block; margin-bottom: 8px; color: #475569; font-size: 13px; }
    .info-card span { font-size: 16px; }
    .option { border-left: 4px solid #2563eb; }
    .option h3 { margin: 0 0 10px; font-size: 18px; }
    .option p { margin: 6px 0; color: #475569; }
    .price { color: #dc2626 !important; font-size: 20px; font-weight: 700; }
    .tool { display: inline-block; margin: 4px 8px 4px 0; padding: 5px 9px; border-radius: 999px; background: #ecfdf5; color: #047857; font-size: 13px; }
    footer { margin-top: 22px; text-align: center; color: #94a3b8; font-size: 13px; }
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>一站式智能订票 Agent</h1>
      <p class="subtitle">用自然语言描述你的出行需求，系统会自动理解条件、调用交通查询工具并筛选方案。</p>
    </section>

    <section class="panel">
      <label for="message">请输入你的出行需求</label>
      <textarea id="message" placeholder="例如：9月20日早上8点以后从太原去北京，预算500元，优先高铁，不接受中转"></textarea>
      <div class="actions">
        <button id="submit">查询出行方案</button>
        <button id="new-chat" type="button" style="color:#1d4ed8;background:#eff6ff;">开始新对话</button>
        <button id="provider-status-button" type="button" style="color:#047857;background:#ecfdf5;">查看服务状态</button>
        <a class="link-button" href="/api-docs" target="_blank">开发接口文档</a>
        <span class="hint">示例：<span class="example" id="example">明天从太原去北京，预算500元，优先高铁</span></span>
      </div>
      <div id="status" class="status hidden"></div>
      <div id="provider-status" class="status hidden" aria-live="polite"></div>
    </section>

    <section id="result" class="panel hidden">
      <h2 class="section-title">解析出的出行条件</h2>
      <div id="parsed" class="grid"></div>
      <div id="tools-block" class="hidden" style="margin-top: 22px;">
        <h2 class="section-title">本次调用的查询工具</h2>
        <div id="tools"></div>
      </div>
      <div style="margin-top: 22px;">
        <h2 class="section-title">推荐方案</h2>
        <div id="options" class="grid"></div>
      </div>
    </section>

    <footer>当前使用本地 Ollama 模型和 Mock 交通数据进行演示</footer>
  </main>

  <script>
    const labels = {
      origin: "出发地", destination: "目的地", travel_date: "出发日期",
      depart_after: "最早出发时间", budget: "预算上限", transport_types: "交通方式",
      allow_transfer: "允许中转", max_transfers: "最多中转次数", preference: "偏好"
    };
    const transportNames = { train: "火车/高铁", flight: "飞机", taxi: "出租车" };
    const escapeHtml = value => String(value ?? "").replace(/[&<>\"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#39;"}[char]));
    const message = document.getElementById("message");
    const submit = document.getElementById("submit");
    let sessionId = localStorage.getItem("ticket_agent_session_id");
    const status = document.getElementById("status");
    const result = document.getElementById("result");

    document.getElementById("example").onclick = () => {
      message.value = "明天从太原去北京，预算500元，优先高铁";
    };

    document.getElementById("new-chat").onclick = async () => {
      if (sessionId) {
        await fetch(`/agent/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      }
      sessionId = null;
      localStorage.removeItem("ticket_agent_session_id");
      message.value = "";
      result.classList.add("hidden");
      showStatus("已开始新对话。");
    };

    document.getElementById("provider-status-button").onclick = async () => {
      const panel = document.getElementById("provider-status");
      panel.className = "status";
      panel.textContent = "正在读取服务状态……";
      try {
        const response = await fetch("/providers/status");
        const providers = await response.json();
        panel.innerHTML = providers.map(item => {
          const state = item.circuit_state === "closed" ? "正常" : item.circuit_state === "open" ? "已熔断" : "等待恢复";
          return `<span class="tool">${escapeHtml(item.transport_type)}：${escapeHtml(item.mode)}，${escapeHtml(state)}，成功 ${escapeHtml(item.success_calls)} 次，失败 ${escapeHtml(item.failed_calls)} 次</span>`;
        }).join("");
      } catch (error) {
        panel.textContent = `读取失败：${error.message}`;
        panel.className = "status error";
      }
    };

    function showStatus(text, isError = false) {
      status.textContent = text;
      status.className = `status${isError ? " error" : ""}`;
      status.classList.remove("hidden");
    }

    function renderParsed(parsed) {
      const fields = Object.entries(parsed).map(([key, value]) => {
        if (value === null || value === undefined || value === "") return "";
        let display = value;
        if (key === "transport_types" && Array.isArray(value)) display = value.map(item => transportNames[item] || item).join("、");
        if (key === "allow_transfer") display = value ? "可以中转" : "不接受中转";
        if (key === "budget") display = `${value} 元`;
        return `<div class="info-card"><strong>${labels[key] || escapeHtml(key)}</strong><span>${escapeHtml(display)}</span></div>`;
      }).join("");
      document.getElementById("parsed").innerHTML = fields || "<div class=\"hint\">暂未解析出条件</div>";
    }

    function renderTools(toolCalls) {
      const block = document.getElementById("tools-block");
      if (!toolCalls || !toolCalls.length) { block.classList.add("hidden"); return; }
      block.classList.remove("hidden");
      document.getElementById("tools").innerHTML = toolCalls.map(call => {
        const name = call.name.replace("search_", "");
        const display = transportNames[name] || name;
        const state = call.status === "success" ? `调用成功，返回 ${call.result_count} 条` : `调用失败：${call.error || "未知错误"}`;
        return `<span class="tool">${escapeHtml(display)}：${escapeHtml(state)}</span>`;
      }).join("");
    }

    function renderOptions(options) {
      const container = document.getElementById("options");
      if (!options || !options.length) {
        container.innerHTML = "<div class=\"hint\">没有找到符合条件的出行方案。</div>";
        return;
      }
      container.innerHTML = options.map(item => `
        <article class="option">
          <h3>${escapeHtml(transportNames[item.transport_type] || item.transport_type)} · ${escapeHtml(item.provider)}</h3>
          <p>路线：${escapeHtml(item.origin)} → ${escapeHtml(item.destination)}</p>
          <p>时间：${escapeHtml(item.departure_time.replace("T", " "))} 至 ${escapeHtml(item.arrival_time.replace("T", " "))}</p>
          <p>耗时：${escapeHtml(item.duration_minutes)} 分钟　中转：${escapeHtml(item.transfers)} 次</p>
          <p>座位：${escapeHtml(item.seat_type || "未提供")}　余票：${item.ticket_count == null ? "未提供" : escapeHtml(item.ticket_count + " 张")}</p>
          <p>状态：${item.is_available ? "可以预订" : "暂不可预订"}</p>
          <p class="price">${escapeHtml(item.price)} 元</p>
        </article>`).join("");
    }

    submit.onclick = async () => {
      const text = message.value.trim();
      if (!text) { showStatus("请先输入出行需求。", true); return; }
      submit.disabled = true;
      result.classList.add("hidden");
      showStatus("正在理解需求并查询方案，请稍候……");
      try {
        const payload = { message: text };
        if (sessionId) payload.session_id = sessionId;
        const response = await fetch("/agent/plan", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "请求失败，请检查服务状态。");
        sessionId = data.session_id;
        localStorage.setItem("ticket_agent_session_id", sessionId);
        renderParsed(data.parsed_request);
        renderTools(data.tool_calls);
        renderOptions(data.options);
        result.classList.remove("hidden");
        showStatus(data.clarification || data.message);
      } catch (error) {
        showStatus(error.message, true);
      } finally {
        submit.disabled = false;
      }
    };
  </script>
</body>
</html>
"""
    )
