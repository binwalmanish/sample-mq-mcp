# IBM MQ MCP Servers

This repository contains two IBM MQ Model Context Protocol (MCP) servers that expose IBM MQ monitoring and management capabilities to AI agents (such as Claude). Both servers communicate with IBM MQ's REST API and MQSC commands over HTTPS.

---

## Servers Overview

| File | Server Name | Access Level | Use Case |
|------|-------------|--------------|----------|
| [mqmcpserver_enterprise.py](mqmcpserver_enterprise.py) | `mqmcpserver-enterprise` | Full read access | Operations teams needing deep diagnostics |
| [mqmcpserver_readonly_secure.py](mqmcpserver_readonly_secure.py) | `mqmcpserver-enterprise-readonly` | Strictly read-only (security hardened) | AI agents, auditors, read-only operators |

---

## mqmcpserver_enterprise.py

Enterprise-grade MCP server designed for large-scale MQ infrastructure (200+ servers, 500+ queue managers). Provides comprehensive monitoring, analytics, and health reporting tools.

### Tools

#### `discover_all_queue_managers`

Discovers and lists all queue managers across all configured MQ servers.

- **Parameters:** None
- **Returns:** Discovery report grouped by status and region, including running state, environment, and criticality metadata
- **MQSC/API:** `GET /qmgr/`
- **Use for:** Initial infrastructure discovery, health checks across all QMs

---

#### `health_check_all_queues`

Comprehensive health check of all queues on a queue manager. Flags queues above the depth threshold and queues with no active consumers.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name, e.g. `QM1`
  - `depth_threshold` (int, default `80`) — Alert if queue depth exceeds this percentage
- **Returns:** Health report with alerts (HIGH_DEPTH, NO_CONSUMERS), summary statistics, and top 10 queues by depth
- **MQSC command:** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS`
- **Use for:** Daily health checks, incident investigation, capacity monitoring

---

#### `monitor_channel_status`

Monitors all channels (sender, receiver, server, cluster) on a queue manager.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** Channel status report categorized as Running, Inactive, Retrying, or Stopped. Highlights channels in RETRY or STOPPED states
- **MQSC command:** `DISPLAY CHSTATUS(*) ALL`
- **Use for:** Connectivity troubleshooting, network issue detection, cluster health

---

#### `analyze_queue_depth_trends`

Analyzes current queue depths to identify capacity concerns and growing queues.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
  - `queue_pattern` (str, default `*`) — Queue name filter pattern
- **Returns:** Capacity analysis with per-queue utilization percentages, severity classification (INFO / WARNING / CRITICAL), and recommendations
- **MQSC command:** `DISPLAY QLOCAL(<pattern>) CURDEPTH MAXDEPTH MSGAGE`
- **Use for:** Capacity planning, identifying slow consumers, predicting issues

---

#### `get_application_connections`

Lists all active application connections to a queue manager.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** Total active connection count and connection detail lines (capped at 50 for readability)
- **MQSC command:** `DISPLAY CONN(*) ALL`
- **Use for:** Security auditing, troubleshooting application issues, capacity planning

---

#### `check_dead_letter_queues`

Inspects the Dead Letter Queue (DLQ) and reports message accumulation.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** DLQ depth and remediation recommendations if messages are present
- **MQSC command:** `DISPLAY QLOCAL(SYSTEM.DEAD.LETTER.QUEUE) CURDEPTH MAXDEPTH`
- **Use for:** Troubleshooting message delivery failures, identifying problematic applications

---

#### `monitor_cluster_health`

Monitors MQ cluster health across all configured queue managers.

- **Parameters:**
  - `cluster_name` (str, default `*`) — Cluster name pattern
- **Returns:** Cluster member status from each responding queue manager
- **MQSC command:** `DISPLAY CLUSQMGR(<cluster>) ALL`
- **Use for:** Cluster troubleshooting, ensuring cluster stability, detecting split-brain

---

#### `get_performance_metrics`

Retrieves performance metrics for a queue manager.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** Raw queue manager status data including CPU, memory, and message rate indicators
- **MQSC command:** `DISPLAY QMSTATUS(*) ALL`
- **Use for:** Performance troubleshooting, capacity planning, SLA monitoring

---

#### `generate_capacity_report`

Generates a capacity planning report across all queue managers or a filtered environment.

- **Parameters:**
  - `environment` (str, default `all`) — Filter by `production`, `staging`, `development`, or `all`
- **Returns:** Executive summary with total QM count, queue count, message counts; per-QM breakdown sorted by message volume; and scaling recommendations
- **MQSC command:** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH`
- **Use for:** Monthly capacity reviews, budget planning, infrastructure scaling decisions

---

#### `detect_anomalies`

Detects anomalies in queue manager behavior such as queues at near-capacity or messages with no consumers.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** Anomaly report with CRITICAL and HIGH priority issues categorized by type (CAPACITY, NO_CONSUMER)
- **MQSC command:** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS MSGAGE`
- **Use for:** Proactive issue detection, automated monitoring, incident prevention

---

#### `batch_health_check`

Runs health checks across multiple queue managers in parallel, with optional region and criticality filters.

- **Parameters:**
  - `region` (str, default `all`) — Filter by `us-east`, `us-west`, `eu-west`, or `all`
  - `criticality` (str, default `all`) — Filter by `high`, `medium`, `low`, or `all`
- **Returns:** Aggregated report with total alert count and per-QM status (OK / ALERTS / ERROR)
- **Delegates to:** `health_check_all_queues` per matching queue manager
- **Use for:** Daily health checks, executive dashboards, SLA reporting

---

## mqmcpserver_readonly_secure.py

Security-hardened version of the enterprise server. All MQSC commands pass through a validation layer that enforces a strict read-only policy before execution. This server is safe to expose to AI agents, auditors, or any user who should not be able to modify MQ infrastructure.

### Tools

#### `discover_all_queue_managers`

Same as the enterprise version but explicitly uses only HTTP `GET` requests.

- **Parameters:** None
- **Returns:** Discovery report with running status, region, environment, and criticality per QM
- **API method:** `GET /qmgr/` only

---

#### `health_check_all_queues`

Same functionality as the enterprise version, executed through the read-only security wrapper.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
  - `depth_threshold` (int, default `80`) — Alert percentage threshold
- **Returns:** Health report, or a security violation message if the underlying command is blocked
- **MQSC command (validated):** `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS`

---

#### `monitor_channel_status`

Same functionality as the enterprise version, executed through the read-only security wrapper.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** Channel status report, or a security violation message if the underlying command is blocked
- **MQSC command (validated):** `DISPLAY CHSTATUS(*) ALL`

---

#### `check_dead_letter_queues`

Same functionality as the enterprise version but explicitly notes that browsing or deleting DLQ messages is not permitted.

- **Parameters:**
  - `qmgr_name` (str) — Queue manager name
- **Returns:** DLQ depth report and recommendations, or a security violation message
- **MQSC command (validated):** `DISPLAY QLOCAL(SYSTEM.DEAD.LETTER.QUEUE) CURDEPTH MAXDEPTH`

---

#### `get_security_policy`

Returns the full security policy document inline — allowed operations, blocked operations, enforcement details, and escalation contacts.

- **Parameters:** None
- **Returns:** Formatted security policy showing allowed MQSC commands, blocked MQSC commands, allowed/blocked REST operations, and change management process

---

## Security Architecture (Read-Only Server)

### How Write Commands Are Blocked

The read-only server enforces a multi-layer security model. Every MQSC command passes through `execute_mqsc_readonly()` before it reaches the IBM MQ REST API.

```
AI Agent Tool Call
       │
       ▼
execute_mqsc_readonly(qmgr_name, command)
       │
       ├─► validate_mqsc_command(command)
       │         │
       │         ├─ Extracts the command verb (first word, uppercased)
       │         ├─ Checks verb against BLOCKED_MQSC_COMMANDS blocklist
       │         ├─ Checks verb against ALLOWED_MQSC_COMMANDS allowlist
       │         └─ Scans full command text for dangerous keyword patterns
       │
       ├─ If BLOCKED → log_security_event(CRITICAL) → return security violation message
       │
       └─ If ALLOWED → log_security_event(INFO) → send to IBM MQ REST API
```

### Blocked MQSC Commands

The following command verbs are unconditionally blocked:

| Command | Reason |
|---------|--------|
| `DEFINE` | Creates queues, channels, processes, etc. |
| `ALTER` | Modifies existing MQ object definitions |
| `DELETE` | Removes MQ objects |
| `CLEAR` | Clears all messages from a queue |
| `START` | Starts channels, listeners, services |
| `STOP` | Stops channels, listeners, services |
| `RESET` | Resets channel statistics or sequence numbers |
| `REFRESH` | Refreshes cluster or security configuration |
| `SUSPEND` | Suspends a queue manager from a cluster |
| `RESUME` | Resumes a suspended queue manager |
| `PING` | Sends a ping through a channel (side-effecting) |
| `RESOLVE` | Resolves in-doubt transactions |
| `MOVE` | Moves messages between queues |
| `SET` | Changes system parameters |
| `ARCHIVE` | Archives log files |
| `RECOVER` | Recovers objects or transactions |
| `RCDMQIMG` | Records MQ image for recovery |
| `RCRMQOBJ` | Recreates MQ objects from image |

### Allowed MQSC Commands

Only one command verb is permitted:

| Command | Description |
|---------|-------------|
| `DISPLAY` | Read object definitions and runtime status |

In addition to the blocklist check, the command text is scanned for dangerous keywords (`CLEAR`, `DELETE`, `ALTER`, `DEFINE`, `START`, `STOP`, `RESET`) using regex to prevent injection via embedded subcommands.

### HTTP Method Restriction

Only `GET` is permitted for direct REST API calls. `POST`, `PUT`, `DELETE`, and `PATCH` are blocked. (Note: the MQSC execution endpoint uses `POST` by IBM MQ's REST API design, but the *content* of that POST is validated to contain only `DISPLAY` commands.)

### Blocked REST Endpoints

| Endpoint Pattern | Reason |
|------------------|--------|
| `/messaging/` | Message put and get operations |
| `/action/qmgr/*/mqsc` | MQSC execution (validated separately) |

### Security Audit Logging

Every command execution — whether allowed or blocked — is logged via `log_security_event()` to stderr with a structured format:

```
[<ISO timestamp>] SECURITY [<SEVERITY>] <EVENT_TYPE>: <details>
```

| Event Type | Severity | Trigger |
|------------|----------|---------|
| `ALLOWED_MQSC_COMMAND` | INFO | Command passed validation and was sent to MQ |
| `BLOCKED_MQSC_COMMAND` | CRITICAL | Command was rejected by the security layer |
| `MQSC_EXECUTION_ERROR` | WARNING | Allowed command failed at the MQ REST API level |

In production, redirect these logs to a SIEM or security monitoring system.

### Security Violation Response

When a blocked command is attempted, the tool returns a formatted error instead of executing anything:

```
╔════════════════════════════════════════════════════════════════════════════╗
║                          SECURITY POLICY VIOLATION                          ║
╚════════════════════════════════════════════════════════════════════════════╝

❌ COMMAND BLOCKED: BLOCKED: 'ALTER' commands are not allowed...

Requested Command: ALTER QLOCAL(MY.QUEUE) MAXDEPTH(10000)
Queue Manager: QM1
Timestamp: 2025-01-15T10:30:00.000000
...
```

The event is also written to the audit log before returning to the caller.

---

## Configuration

Both servers share the same `MQ_SERVERS` configuration dictionary:

```python
MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd",
        "region": "us-east",
        "environment": "production",
        "criticality": "high"
    },
    ...
}
```

Add additional queue managers by extending this dictionary. For the read-only server, use a dedicated read-only IBM MQ service account with minimal permissions (OAM `+inq +browse` on objects, no `+put`, `+get`, `+set`, or administration rights).

---

## Running the Servers

```bash
# Enterprise server
python mqmcpserver_enterprise.py

# Read-only security hardened server
python mqmcpserver_readonly_secure.py
```

Both servers use `stdio` transport for integration with MCP clients such as Claude Desktop.

### Dependencies

```bash
pip install mcp httpx
```

---

## Choosing the Right Server

| Scenario | Recommended Server |
|----------|--------------------|
| AI agent / LLM integration | `mqmcpserver_readonly_secure.py` |
| Compliance auditing | `mqmcpserver_readonly_secure.py` |
| Read-only operator dashboards | `mqmcpserver_readonly_secure.py` |
| Operations team deep diagnostics | `mqmcpserver_enterprise.py` |
| Capacity planning and trending | Either (enterprise has more tools) |
| Production environments exposed to AI | `mqmcpserver_readonly_secure.py` only |

> **Security Recommendation:** Always deploy `mqmcpserver_readonly_secure.py` when the MCP server is accessible to an AI agent. The enterprise server provides no write-command protection and should only be used in controlled, trusted contexts.
