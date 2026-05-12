---
name: mq-mcp-skill
description: >
  Use when working with IBM MQ infrastructure via the MCP server tools.
  Trigger on: "check MQ", "queue depth", "channel status", "dead letter queue",
  "queue manager health", "MQ performance", "cluster health", "MQ capacity",
  "why are messages stuck", "which queues are full", "application connections to MQ",
  "MQ anomaly", "batch health check", "discover queue managers".
---

# IBM MQ MCP Skill

## Servers

| Server File | MCP Server Name | Access | Use When |
|---|---|---|---|
| `mqmcpserver_enterprise.py` | `mqmcpserver-enterprise` | Full read | Operations team, deep diagnostics, trending |
| `mqmcpserver_readonly_secure.py` | `mqmcpserver-enterprise-readonly` | Read-only (hardened) | AI agents, auditors, automated monitoring |

**Default:** Always prefer `mqmcpserver-enterprise-readonly` unless the task explicitly requires a tool only in the enterprise server (trending, anomaly detection, capacity report, cluster health, application connections, batch checks).

## Connection

- **REST API base:** `https://localhost:9443/ibmmq/rest/v3/admin/` (QM1) · `https://localhost:9444/ibmmq/rest/v3/admin/` (QM2)
- **Auth:** HTTP Basic — `admin` / `passw0rd`
- **TLS:** `verify=False` (self-signed cert in dev)
- **Transport:** MCP stdio — invoke tools via MCP client, not direct HTTP

## Queue Managers

| Name | URL Port | Region | Environment | Criticality |
|---|---|---|---|---|
| QM1 | 9443 | us-east | production | high |
| QM2 | 9444 | us-west | production | high |

## Tools — Read-Only Server (`mqmcpserver-enterprise-readonly`)

### `discover_all_queue_managers()`
Lists all queue managers across all configured servers with state, region, environment, criticality.
- **Trigger:** "list queue managers", "what QMs are running", "discover MQ"
- **API:** `GET /ibmmq/rest/v3/admin/qmgr/`
- **Returns:** Running / stopped count grouped by region

### `health_check_all_queues( qmgr_name, depth_threshold=80 )`
Full queue health scan — flags HIGH_DEPTH (above threshold) and NO_CONSUMERS (messages waiting with no active consumer).
- **Trigger:** "health check QM1", "are any queues full", "queue report"
- **MQSC:** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS`
- **Returns:** Alert list + top 10 queues by depth + summary stats

### `monitor_channel_status( qmgr_name )`
Shows all channels — Running, Inactive, Retrying, Stopped. Highlights RETRY and STOPPED channels.
- **Trigger:** "channel status", "why can't app connect", "is channel down", "network issues MQ"
- **MQSC:** `DISPLAY CHSTATUS(*) ALL`
- **Returns:** Counts by state + detail lines for retrying/stopped channels

### `check_dead_letter_queues( qmgr_name )`
Reads `SYSTEM.DEAD.LETTER.QUEUE` depth and gives remediation steps if messages are present.
- **Trigger:** "DLQ", "dead letter queue", "messages not delivered", "delivery failure"
- **MQSC:** `DISPLAY QLOCAL(SYSTEM.DEAD.LETTER.QUEUE) CURDEPTH MAXDEPTH`
- **Returns:** DLQ depth + recommendations (cannot browse/delete — read-only policy)

### `get_security_policy()`
Returns the full read-only security policy: allowed commands, blocked commands, escalation contacts.
- **Trigger:** "what can this server do", "why was my command blocked", "security policy"
- **Returns:** Inline policy document with allowed/blocked MQSC and REST operations

## Tools — Enterprise Server (`mqmcpserver-enterprise`)

Includes all read-only server tools above plus:

### `analyze_queue_depth_trends( qmgr_name, queue_pattern='*' )`
Capacity analysis — classifies queues as INFO (>50%), WARNING (>80%), CRITICAL (>90%).
- **Trigger:** "trending", "which queues are growing", "capacity planning", "predict issues"
- **MQSC:** `DISPLAY QLOCAL(<pattern>) CURDEPTH MAXDEPTH MSGAGE`

### `get_application_connections( qmgr_name )`
Lists all active application connections with user, IP, and connection detail.
- **Trigger:** "who is connected to MQ", "application connections", "security audit MQ"
- **MQSC:** `DISPLAY CONN(*) ALL`

### `monitor_cluster_health( cluster_name='*' )`
Queries every configured queue manager for cluster member status. Good for split-brain detection.
- **Trigger:** "cluster health", "MQ cluster status", "cluster split-brain"
- **MQSC:** `DISPLAY CLUSQMGR(*) ALL` (per QM)

### `get_performance_metrics( qmgr_name )`
Queue manager status including CPU, memory, message rate indicators.
- **Trigger:** "MQ performance", "slow MQ", "throughput", "SLA monitoring"
- **MQSC:** `DISPLAY QMSTATUS(*) ALL`

### `generate_capacity_report( environment='all' )`
Cross-QM capacity report with total queue count, message count, per-QM breakdown, and scaling recommendations. Filter by `production` / `staging` / `development` / `all`.
- **Trigger:** "capacity report", "monthly MQ review", "infrastructure sizing", "budget planning"
- **MQSC:** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH` (per QM)

### `detect_anomalies( qmgr_name )`
Flags CRITICAL (queue >95% full) and HIGH (>100 messages, zero consumers) anomalies.
- **Trigger:** "anomaly", "something wrong with MQ", "proactive check", "anything unusual"
- **MQSC:** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS MSGAGE`

### `batch_health_check( region='all', criticality='all' )`
Parallel health check across all matching queue managers. Returns OK / ALERTS / ERROR per QM.
- **Trigger:** "check all QMs", "dashboard", "SLA report", "executive summary"
- **Filters:** `region` = us-east · us-west · eu-west · all  |  `criticality` = high · medium · low · all
- **Delegates to:** `health_check_all_queues` per matched QM

## MQSC Reference (DISPLAY-only — read-only server)

| Command | Purpose |
|---|---|
| `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS` | All local queue depths + consumer/producer counts |
| `DISPLAY CHSTATUS(*) ALL` | All channel runtime statuses |
| `DISPLAY CONN(*) ALL` | All application connections |
| `DISPLAY CLUSQMGR(*) ALL` | Cluster queue manager members |
| `DISPLAY QMSTATUS(*) ALL` | Queue manager performance status |
| `DISPLAY QLOCAL(SYSTEM.DEAD.LETTER.QUEUE) CURDEPTH MAXDEPTH` | Dead letter queue depth |

## Blocked Operations (Read-Only Server)

The following are rejected before reaching IBM MQ. Never attempt them through the read-only server:

| Blocked Verb | What it would do |
|---|---|
| `DEFINE` | Create queues / channels / objects |
| `ALTER` | Modify object definitions |
| `DELETE` | Remove MQ objects |
| `CLEAR` | Empty a queue |
| `START` / `STOP` | Control channels and listeners |
| `RESET` | Reset channel sequence numbers / statistics |
| `REFRESH` | Refresh cluster or security config |
| `SUSPEND` / `RESUME` | Cluster membership control |
| `SET` | Change system parameters |
| `PING` / `RESOLVE` / `MOVE` | Side-effecting operations |

For any write operation: direct the user to IBM MQ Console, `runmqsc` CLI, or MQ Explorer, or raise a change request.

## Rules

- Always call `get_security_policy()` first if a user asks why a command was rejected
- Use `depth_threshold=90` for high-criticality queue managers instead of the default 80
- When a user gives a queue name pattern (e.g. `APP.*`), pass it to `analyze_queue_depth_trends` not `health_check_all_queues` (which always scans all queues)
- `batch_health_check` runs checks in parallel — prefer it over looping `health_check_all_queues` manually
- If `SECURITY POLICY VIOLATION` appears in a tool response, do not retry the same command — log it and explain to the user what was blocked and why
- All operations are audit-logged to stderr; do not try to suppress or work around this
- The read-only server cannot browse, get, or delete individual messages — for message-level investigation, escalate to an MQ administrator
