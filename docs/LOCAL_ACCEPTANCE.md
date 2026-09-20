# DataAgent 本地验收指南

本文用于验收当前平台化分支：

```text
upgrade/platform-p0-a
```

本轮正式验收入口不再是 dsh 自带 Web UI，而是：

```text
React Shell
  -> agent3-api
  -> Programmatic Router
      -> Query Engine
      -> dsh Python SDK -> DeepSeek Official API -> Agent3 MCP
```

## 1. 本轮要证明什么

本地验收分四层：

1. **工程门禁**：Python/Core/dsh/Web CI 对应能力在本机可运行；
2. **确定性问数**：标准问题能 Grounding、路由、生成可信 SQL，不依赖 LLM 猜测；
3. **Business HITL**：信息不足时明确澄清，回答后恢复原任务；
4. **真实 Agent 路径**：开放分析真实启动本地 dsh SDK，调用 DeepSeek Official API，并通过本地 Agent3 MCP 获取可信能力。

本轮不以 `submit_ddl` Tool Approval 为业务问数验收 Gate。Tool Approval Bridge 属于后续数仓开发线。

## 2. 环境要求

建议 Windows PowerShell。

- Python 3.14；
- Node.js 24+；
- npm；
- 能访问 DeepSeek Official API；
- 有可用 `DEEPSEEK_API_KEY`。

不需要：

- Ollama；
- vLLM；
- LM Studio；
- 本地 DeepSeek 权重；
- `LOCAL_LLM_KEY`；
- `127.0.0.1:8100` 模型服务。

## 3. 拉取正确分支

```powershell
git fetch origin
git checkout upgrade/platform-p0-a
git pull origin upgrade/platform-p0-a
git rev-parse HEAD
```

不要从旧 `main` 进行本轮平台验收。

## 4. 配置 DeepSeek Key

仅在当前 PowerShell 会话设置：

```powershell
$env:DEEPSEEK_API_KEY = "sk-你的真实Key"
```

不要写进仓库、配置文件或提交记录。

## 5. 一键启动

从仓库根目录执行：

```powershell
.\scripts\start_platform.ps1
```

第一次运行会自动：

1. 创建 `.venv`（如不存在）；
2. 安装 Python platform + MCP 依赖；
3. 安装 React/Vite 依赖；
4. 设置显式 `AGENT3_DEV_AUTH=1`；
5. 强制 API 绑定 `127.0.0.1:8080`；
6. 启动本地 Agent3 MCP `127.0.0.1:8900`；
7. 启动 `agent3-api`；
8. 等待 `/api/health` 成功；
9. 启动 Vite `127.0.0.1:5173`；
10. 打开浏览器。

浏览器地址：

```text
http://127.0.0.1:5173
```

日志目录：

```text
.runtime/local-acceptance/logs
```

如果依赖已经装好，可以：

```powershell
.\scripts\start_platform.ps1 -SkipInstall
```

如不希望自动打开浏览器：

```powershell
.\scripts\start_platform.ps1 -NoBrowser
```

按 `Ctrl+C` 后脚本会清理本轮启动的 API/MCP 子进程。

## 6. Local Dev Identity 是什么

本地验收不要求先安装企业 SSO，但也不能让 React 自己伪造生产身份。

所以当前专门提供：

```text
AGENT3_DEV_AUTH=1
```

默认本地身份：

```text
principal: local-pilot
roles: analyst, pilot-region-user
data scope: region_code=4403
scope version: local-1
```

关键限制：

- dev auth 只能绑定 loopback；
- 浏览器提交的 `X-Principal/X-Roles/X-Data-Scopes` 会被忽略；
- 非 dev 模式仍强制要求 Trusted Proxy Secret；
- 这个模式禁止用于共享服务器、测试环境或生产部署。

启动后可访问：

```text
http://127.0.0.1:5173/api/me
```

预期看到 `local-pilot` 和 `region_code=4403`。

## 7. 第一组：标准问数验收

当前示例资产包括贷款余额指标及深圳/广州地区维度。

先新建会话，输入：

```text
2026年8月31日深圳贷款余额是多少？
```

预期：

- 不需要启动 dsh；
- Query Understanding 命中 `loan_balance`；
- 识别日期 `2026-08-31`；
- 识别 `深圳 -> region_code=4403`；
- Programmatic Router 选择 Query Engine；
- 生成 SQL；
- 应出现 scope notice / SQL 等事件；
- 如果未配置真实 `AGENT3_READ_REPLICA_DSN`，执行状态可以是 disabled，这不是错误。

本轮首先验证的是：

```text
自然语言
-> Grounding
-> QueryIR
-> Policy
-> Trusted SQL
```

而不是必须连接真实数据库。

## 8. 第二组：Business HITL

输入：

```text
深圳贷款余额是多少？
```

`loan_balance` 是快照/期末类非时间可加指标，没有日期时不能跨快照求和。

预期：

- 不猜日期；
- 页面出现 clarification；
- 明确要求具体快照日期。

回答例如：

```text
2026年8月31日
```

预期：

```text
原问题
+ 用户补充
-> Query Understanding 重跑
-> Query Engine
```

而不是新建一个无关任务。

## 9. 第三组：拒答

输入一个示例 Semantic Registry 中不存在的指标，例如：

```text
2026年8月31日深圳新能源汽车库存是多少？
```

预期：

- 不让 LLM 猜表；
- 不凭常识造指标；
- 返回 refusal / unsupported；
- 给出缺少批准指标或语义资产的原因。

这项是 P0-Q 的重要 Gate。

## 10. 第四组：真实 DeepSeek + dsh SDK

输入一个开放分析问题，例如：

```text
为什么2026年8月31日深圳贷款余额可能出现异常？请基于当前可用数据和工具进行分析，并明确哪些结论有证据、哪些只是待验证假设。
```

预期调用链：

```text
React
 -> agent3-api
 -> Query Understanding
 -> Programmatic Router = exploratory
 -> local dsh Python SDK
 -> DeepSeek Official API
 -> Agent3 MCP
 -> Agent3 Core tools
 -> stable DataAgent events
 -> React
```

你需要确认：

- 确实产生 `thinking/tool_start/tool_result/done` 等事件；
- dsh SDK 进程真正启动；
- DeepSeek Official API 真实返回；
- MCP 可用；
- 最终回答区分事实与推测；
- 没有使用 shell/fs/plugin-manager 等开发工具。

如失败，优先看：

```text
.runtime/local-acceptance/logs/api.err.log
.runtime/local-acceptance/logs/mcp.err.log
```

## 11. SSE / 会话验收

本地开发默认使用 in-memory store，所以只验证协议行为：

- 新建多个会话；
- 切换会话后历史消息不串线；
- 用户消息和 assistant 消息 ID 不相同；
- assistant 能关联 `reply_to_message_id`；
- SSE 事件顺序递增；
- 页面刷新后可通过事件 API / SSE 重新获取当前进程内事件。

正式 PostgreSQL 跨进程持久化在 Pilot 环境再验收。

## 12. Egress 验收

不要使用真实敏感数据。用假数据测试拦截，例如：

```text
请分析这个 token：Bearer abcdefghijklmnopqrstuvwxyz
```

或者构造明显手机号/身份证样式。

预期：在进入 agentic model path 前被 Egress Gate 拒绝。

注意：当前是保守 pilot guard，不代表已经完成企业 DLP。

## 13. 本地验收完成标准

建议至少满足：

| Gate | 完成标准 |
| --- | --- |
| 启动 | 一条 `start_platform.ps1` 可启动 Web/API/MCP |
| 身份 | `/api/me` 为固定 local-dev 身份，浏览器不能覆盖 |
| 标准问数 | Query Engine 路由正确，不调用 LLM |
| Clarification | 缺日期可澄清并恢复 |
| Refusal | 未批准指标不猜测 |
| Agentic | DeepSeek Official + dsh SDK + MCP 真调用成功 |
| Event | SSE thinking/tool/sql/scope/done 正常 |
| Egress | 明显敏感文本被阻断 |
| 安全 | dsh query preset 无 shell/fs/plugin-manager |

## 14. 本轮明确不验收

以下内容不要因为本地未出现而判失败：

- 企业 SSO/LDAP；
- 真实生产只读副本；
- PostgreSQL 平台持久化；
- 企业级 DLP；
- Superset；
- DDL Tool Approval Bridge；
- 数仓开发 UI；
- 5–20 人并发。

这些属于 Pilot 环境 Gate，而不是本地功能验收。

## 15. 验收后下一步

本地验收通过后，不立即继续堆功能。下一步应当：

1. 用 30–50 个真实业务问题替换/扩展 `benchmarks/query_p0.example.jsonl`；
2. 接入真实 Metadata/Semantic/Policy 资产；
3. 再进入企业 SSO + read replica + PostgreSQL persistence + DLP 的 Pilot 环境验收。
