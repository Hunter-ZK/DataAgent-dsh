# 本地使用与验收指南

本文用于对 DataAgent-dsh V1 做一次**真实本地验收**。正式验收必须同时满足：

1. Python Core 确定性门禁可独立运行；
2. DeepSeek Harness 使用真实 LLM，而不是 Mock；
3. Agent 必须通过 Agent3 MCP 工具获取 SQL 事实；
4. `submit_ddl` 必须触发 Human-in-the-Loop 审批；
5. 即使人工批准，V1 也不得真正执行生产 DDL。

> 当前仓库的公开 PoC 元数据只包含合成示例表。你可以自行决定验收 SQL，但如果 SQL 引用了仓库未登记的真实企业表，`UNKNOWN_TABLE` / `UNKNOWN_COLUMN` 是正确结果。接真实企业元数据前，不要把它误判为 SQL 引擎错误。

## 1. 环境基线

已在 CI 验证：

- Python 3.14（CI 当前为 3.14.7）
- Node.js 24
- pnpm 11.7.0
- `@deepseek-ai/dsh` 0.1.6-alpha.2

Windows PowerShell 以下命令均从仓库根目录运行。

```powershell
git clone https://github.com/Hunter-ZK/DataAgent-dsh.git
cd DataAgent-dsh

py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[all]"

npm install --global pnpm@11.7.0
Push-Location .\dsh
npm ci
Pop-Location

Push-Location .\guard-plugin
npm ci
npm run build
Pop-Location
```

## 2. 先验收 Python Core

```powershell
python -m pytest
python scripts/check_architecture.py
python examples/stage0_eval.py
```

期望：

- pytest 全绿；
- `architecture boundaries: OK`；
- Stage-0 Evaluation 显示全部通过。

CLI 可以直接审查你自己写的 SQL：

```powershell
agent3 validate "SELECT ..."
```

如需按公开示例指标检查业务语义：

```powershell
agent3 validate "SELECT ..." --metric loan_balance
```

公开 PoC 中可直接识别的核心表为 `dw.dwd_loan_snapshot`，字段包括 `dt`、`org_id`、`region_code`、`product_id`、`balance_amt`、`status`。

建议至少覆盖以下行为，但具体 SQL 由验收人自行设计：

| 验收点 | 期望 |
| --- | --- |
| 正常 SQL | 无 error 时 `valid=true` |
| 不存在字段 | `UNKNOWN_COLUMN` |
| 不存在表 | `UNKNOWN_TABLE` |
| 缺少分区过滤 | `NO_PARTITION_FILTER` advisory/warning |
| `DROP/TRUNCATE` | `DROP_OR_TRUNCATE` + `BLOCK` |
| MaxCompute `INSERT OVERWRITE` 缺 `TABLE` | `MAXCOMPUTE_INSERT_OVERWRITE_TABLE_REQUIRED` + `AUTO_FIX` |
| `loan_balance` 缺强制口径 | `MISSING_MANDATORY_FILTER` |
| `loan_balance` 跨多个快照日聚合 | `NON_ADDITIVE_OVER_TIME` |

## 3. 准备真实 LLM

DataAgent profile 默认连接一个本机/内网 OpenAI-compatible 推理服务：

```text
http://127.0.0.1:8100/v1
model id: deepseek-v3-local
```

你必须先确保这里有**真实模型服务**。V1 验收不接受 Mock LLM。

如果你的推理服务地址或模型 ID 不同，修改：

```text
dsh/profile/cordis.patch.yml
```

中的：

- `baseURL`
- `models[].id`
- `agent-default-model.model`

然后设置凭据。即使本地推理服务不校验 key，也建议保留一个占位值：

```powershell
$env:LOCAL_LLM_KEY = "local-placeholder"
```

## 4. 初始化 DataAgent dsh profile

使用独立的 Harness Home，避免污染你已有的 dsh 配置：

```powershell
$env:DSH_HOME = "$env:LOCALAPPDATA\DataAgent-dsh\dsh-home"
$env:DSH_TELEMETRY_MODE = "DISABLED"
```

第一次初始化 profile：

```powershell
.\dsh\node_modules\.bin\dsh.cmd --profile dataagent --from-default-profile web --dump-config > "$env:TEMP\dataagent-initial-config.txt"
```

安装本地 Guard bundle：

```powershell
.\dsh\node_modules\.bin\dsh.cmd plugin --profile dataagent add "$PWD\guard-plugin"
```

覆盖 DataAgent profile：

```powershell
Copy-Item .\dsh\profile\cordis.patch.yml "$env:DSH_HOME\profiles\dataagent\cordis.patch.yml" -Force
```

检查最终合成配置：

```powershell
.\dsh\node_modules\.bin\dsh.cmd --profile dataagent --dump-config `
  1> "$env:TEMP\dataagent-effective-config.txt" `
  2> "$env:TEMP\dataagent-config.err"

Get-Content "$env:TEMP\dataagent-config.err"
```

`dataagent-config.err` 不应出现：

- `unmatched`
- `not found`
- `failed to resolve`

当前 `dataagent-query` preset 是仓库自带的受限业务问数模式，刻意不暴露 bash、pwsh、文件写入和插件管理工具。

## 5. 启动 Agent3 MCP

打开第二个 PowerShell 窗口，同样进入仓库、激活虚拟环境：

```powershell
cd <你的 DataAgent-dsh 路径>
.\.venv\Scripts\Activate.ps1
$env:AGENT3_MCP_POC_MODE = "1"
python -m agent3.adapters.mcp.server
```

PoC MCP 监听：

```text
http://127.0.0.1:8900/mcp
```

可另开窗口检查端口：

```powershell
Test-NetConnection 127.0.0.1 -Port 8900
```

`TcpTestSucceeded` 应为 `True`。

> `AGENT3_MCP_POC_MODE=1` 使用静态 PoC 身份，仅用于隔离环境验收，不能作为生产身份方案。

## 6. 启动 DeepSeek Harness Web

确保：

- 真实 LLM 服务已运行；
- Agent3 MCP 已运行；
- `LOCAL_LLM_KEY`、`DSH_HOME`、`DSH_TELEMETRY_MODE` 已设置。

从**仓库根目录**启动：

```powershell
.\dsh\node_modules\.bin\dsh.cmd --profile dataagent
```

默认 Web 地址：

```text
http://127.0.0.1:3080
```

新会话默认应使用：

```text
dataagent-query
```

## 7. 验收真实 LLM + MCP SQL 闭环

在 Web 会话中粘贴你自己的 SQL，并使用类似指令：

```text
这是本次验收 SQL。
你必须真实调用 Agent3 MCP 工具，不允许只凭模型知识判断。
先调用 validate_sql，再调用 explain_sql。
如果 validate_sql 返回可修复问题，请根据结构化 code / suggestion 修改 SQL，
并再次调用 validate_sql，最多自修复 3 轮。
未经 Agent3 校验通过，不要把候选 SQL 表述为可信 SQL。

SQL：
<在这里粘贴我自己决定的 SQL>
```

验收时不要只看最终文字答案，应确认会话中真实出现工具调用，例如：

```text
mcp__agent3__validate_sql
mcp__agent3__explain_sql
```

如果是标准指标问数，还可以要求 Agent 调用：

```text
mcp__agent3__search_tables
mcp__agent3__get_schema
mcp__agent3__resolve_metric
mcp__agent3__compile_query
```

这一步验证的是：

```text
真实 LLM
  -> dsh Agent Loop
  -> Agent3 MCP
  -> Agent3 Core deterministic evidence
  -> LLM 基于结构化问题自修复
  -> 重新校验
```

## 8. 验收 Human-in-the-Loop

建议做两遍，一遍拒绝、一遍批准。

在 Web 会话中输入：

```text
这是 HITL 验收。
请使用 mcp__agent3__submit_ddl 提交下面的 DDL。
不得使用 bash、shell 或其它旁路。

CREATE TABLE dw.dataagent_hitl_probe (
  id BIGINT
);
```

### 第一次：拒绝

期望：

1. 模型发起 `mcp__agent3__submit_ddl`；
2. Guard Plugin 在工具执行前发起人工审批；
3. 你选择拒绝；
4. 工具不执行，Agent 收到 deny。

### 第二次：允许一次

再次发起同一请求，人工选择 `allowed-once`。

期望：

1. Guard 允许该次 MCP 调用进入 Core；
2. Core 返回：

```json
{
  "accepted": false,
  "approval_required": true,
  "execution_enabled": false
}
```

3. 数据库中不会创建任何表。

这个结果是刻意设计的：它证明了完整 HITL 链路，同时证明 V1 的人工批准**不能越过生产执行边界**。

## 9. 如何判定本地验收通过

一次合格的本地验收至少应同时留下以下证据：

- Python pytest 全绿；
- Architecture Boundary Gate 通过；
- Stage-0 result-set evaluation 通过；
- dsh Web 使用真实模型产生回复；
- 会话里可以看到实际 Agent3 MCP tool call；
- 你自己的 SQL 经过 `validate_sql`；
- SQL 有问题时，模型基于结构化错误做修改并重新验证；
- HITL 拒绝路径有效；
- HITL `allowed-once` 路径有效；
- 即使批准，`submit_ddl` 仍返回 `execution_enabled=false`；
- `dataagent-query` 会话不提供 bash / 文件写入旁路。

## 10. 当前验收边界

本轮 V1 能正式验收的是：

- SQL deterministic validation；
- SQL explain；
- semantic metric resolution；
- deterministic standard-query generation / `compile_query`；
- LLM 根据 Validator 反馈进行多轮 self-fix；
- MCP 工具调用；
- Human-in-the-Loop approval；
- Stage-0 result-set evaluation；
- Guard / profile / security-boundary integration。

以下仍不是 V1 生产能力：

- 真实生产数据库执行；
- 生产 DDL 执行；
- 完整企业身份与 Policy Engine；
- 通用多表 Semantic Compiler；
- 企业级审批/审计存储。

不要用 PoC 的通过来声称这些能力已经上线。
