# Diagram Walkthrough Guide

A step-by-step narrative for presenting or explaining the two IBM MQ MCP architecture diagrams.

---

## Diagram 1 — Architecture & Tool Inventory
**File:** `mq_mcp_architecture_v2.puml`

This diagram is a component view showing the full system from left to right — who calls what, which tools exist in each server, and where every request ultimately lands inside IBM MQ.

---

### Step 1 — The Entry Point: AI Agent / MCP Client (blue, left)

> "Everything starts here. The blue box on the far left represents any MCP client — this could be Claude, another LLM, or a human operator using a tool that speaks the MCP protocol. The client communicates with the MCP servers over standard input/output (stdio transport), which means no network port is needed; the server runs as a child process."

---

### Step 2 — Two Servers Side by Side

> "The client can connect to either of two servers. The green server on the top is the **Enterprise server** (`mqmcpserver_enterprise.py`), which provides full read access with no write restrictions. The orange server below it is the **Read-Only Secure server** (`mqmcpserver_readonly_secure.py`), which is security-hardened and enforces a strict read-only policy. Both servers expose their capabilities as MCP tools — the AI agent calls them by name, just like calling a function."

---

### Step 3 — Enterprise Server: 11 Tools as Rows (green)

> "Inside the Enterprise server you can see 11 tools, each listed as a row. The top line of each row is the function name and its parameters. The second line shows the exact MQSC command or REST API call that function uses when it talks to IBM MQ. For example, `health_check_all_queues` runs `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS` to read the current depth and consumer count of every queue. Reading down the list, the tools cover the full operational lifecycle: discovery, health checks, channel monitoring, trending, application connections, dead letter queues, cluster health, performance metrics, capacity reporting, anomaly detection, and batch operations."

---

### Step 4 — The Special Case: `batch_health_check`

> "The last tool in the Enterprise server — `batch_health_check` — is worth calling out separately. Rather than running a single MQSC command, it uses Python's `asyncio.gather()` to call `health_check_all_queues` in parallel across every queue manager that matches the region and criticality filters. This means one tool call from the AI agent can simultaneously health-check tens or hundreds of queue managers and return an aggregated report."

---

### Step 5 — Read-Only Server: Security Enforcement Layer (red box)

> "Inside the Read-Only server, the first thing to notice is the red box labelled **Security Enforcement Layer**. This contains four components that act as a gate between the AI agent and IBM MQ. Every tool call in this server — except the simple discovery call — must pass through this layer before anything is sent to IBM MQ. The four components are: `validate_mqsc_command` (checks the command), `validate_http_method` (checks the HTTP verb), `log_security_event` (writes the audit trail), and `execute_mqsc_readonly` (the wrapper that orchestrates the other three)."

---

### Step 6 — Read-Only Server: 5 Tools (orange, below the red box)

> "Below the security layer are the five tools the Read-Only server exposes. They are a subset of the Enterprise server's tools — focused on the most common monitoring needs. Notice that each tool description ends with `→ execute_mqsc_readonly(...)` rather than a direct MQSC command. This is intentional: every tool hands off to the security wrapper rather than calling IBM MQ directly, which means the security layer cannot be bypassed."

---

### Step 7 — The Dashed Red Arrows: Routing Through the Security Wrapper

> "Three dashed red arrows connect the tools `health_check_all_queues`, `monitor_channel_status`, and `check_dead_letter_queues` to the `execute_mqsc_readonly` wrapper. The dashes indicate an internal delegation — the tool does not call IBM MQ itself; it passes the MQSC command to the wrapper and waits for a validated response. Only `discover_all_queue_managers` bypasses the wrapper because it uses a plain HTTP GET call, which is validated separately by `validate_http_method`."

---

### Step 8 — The Three-Step Flow Inside the Security Layer

> "Three labeled arrows inside the security layer show the execution order. Step 1: `execute_mqsc_readonly` calls `validate_mqsc_command` to check whether the command verb is on the blocklist or allowlist and to scan for dangerous keywords. Step 2: after validation, `validate_mqsc_command` notifies `log_security_event`, which writes a structured audit record to stderr or a SIEM — regardless of whether the command was allowed or blocked. Step 3: if and only if validation passed, `execute_mqsc_readonly` sends the command to the IBM MQ REST API."

---

### Step 9 — IBM MQ Infrastructure (purple, right)

> "On the far right is the IBM MQ layer. All roads lead here. At the top is the IBM MQ REST API, listening on HTTPS port 9443 for QM1 and port 9444 for QM2, under the path `/ibmmq/rest/v3/admin/`. Below the REST API are the individual queue managers — QM1 in us-east, QM2 in us-west, and a placeholder QMn to indicate the configuration supports as many additional queue managers as needed. The REST API acts as the single gateway; the MCP servers never talk directly to a queue manager — they always go through the REST API."

---

### Step 10 — Reading the Arrow Colors as a Summary

> "The color of an arrow tells you which path a request takes. Blue arrows are Enterprise server calls — direct, unrestricted routes from each tool to the REST API. Orange arrows are Read-Only server calls — they either go through the security layer (dashed red) before reaching the REST API, or directly to the REST API via HTTP GET only. Purple arrows are the REST API's own connections down to each queue manager. If you trace any request from the AI agent, you can follow the arrows through the appropriate path all the way to the queue manager that handles it."

---

---

## Diagram 2 — Security Enforcement Flow
**File:** `mq_security_flow.puml`

This diagram is a sequence view showing time flowing top to bottom. It uses the Read-Only server exclusively and walks through three real-world scenarios to show exactly what happens inside the security layer step by step.

---

### Step 1 — Participants Across the Top

> "Seven participants are arranged left to right across the top of the diagram. The AI Agent (blue) is the caller. The MCP Tool (green) is the named function the agent invokes. The two guard components — `execute_mqsc_readonly` and `validate_mqsc_command` (both red) — form the security layer. `validate_http_method` (red) handles the REST-only path. `log_security_event` (orange) handles audit logging. The IBM MQ REST API (purple) is the target. Vertical lifelines drop down from each participant, and horizontal arrows between them show messages passing in time order."

---

### Step 2 — Scenario 1: An Allowed Command (happy path)

> "The first scenario, shown in a white group box, walks through a successful read-only call to `health_check_all_queues`. The AI agent calls the tool with queue manager `QM1` and a depth threshold of 80 percent. The tool immediately delegates to `execute_mqsc_readonly`, passing the full MQSC command string `DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS`. This is the entry point into the security layer."

---

### Step 3 — Scenario 1: Inside `validate_mqsc_command`

> "The wrapper calls `validate_mqsc_command`. A note box next to this component shows the five checks that run in sequence: the command is normalised to uppercase; the first word — the command verb — is extracted, giving `DISPLAY`; that verb is checked against the blocked list and is not found; it is then checked against the allowed list and is found; finally, the full command text is scanned with a regex for dangerous keywords such as CLEAR, DELETE, or ALTER, and none are found. All five checks pass, so the function returns `(True, "")` — a green light."

---

### Step 4 — Scenario 1: Logging and Execution

> "With validation passed, `execute_mqsc_readonly` calls `log_security_event` with event type `ALLOWED_MQSC_COMMAND` at severity INFO, creating an audit record. The wrapper then sends a POST request to the IBM MQ REST API at `/action/qmgr/QM1/mqsc`, carrying the DISPLAY command in the JSON body with Basic Auth credentials. IBM MQ responds with HTTP 200 and a JSON payload containing the command output. The wrapper prettifies that output and returns it to the tool, which formats it into a health report and hands it back to the AI agent."

---

### Step 5 — Scenario 2: A Blocked Write Command

> "The second scenario, shown in a red-tinted group box, tests what happens when someone tries to run a write command — in this example, `ALTER QLOCAL(MY.QUEUE) MAXDEPTH(10000)`. The flow starts identically: the agent calls the tool, the tool calls `execute_mqsc_readonly`, which calls `validate_mqsc_command`."

---

### Step 6 — Scenario 2: The Blocklist Hit

> "This time the note box inside `validate_mqsc_command` shows a different outcome. The command is normalised and the verb `ALTER` is extracted. On the very next check — the blocked list — a match is found immediately. The note lists all 18 blocked verbs: DEFINE, ALTER, DELETE, CLEAR, START, STOP, RESET, REFRESH, SUSPEND, RESUME, PING, RESOLVE, MOVE, SET, ARCHIVE, RECOVER, RCDMQIMG, and RCRMQOBJ. Because ALTER is on this list, validation fails and the function returns `(False, 'BLOCKED: ALTER commands are not allowed')`."

---

### Step 7 — Scenario 2: IBM MQ Is Never Contacted

> "This is the critical security guarantee. After the failed validation, `execute_mqsc_readonly` calls `log_security_event` with event type `BLOCKED_MQSC_COMMAND` at severity CRITICAL, writing the blocked command and the queue manager name to the audit log. A red note spanning both the wrapper and the IBM MQ column reads: 'IBM MQ REST API is NEVER contacted. Request is dropped at the validation layer.' No network call is made. The wrapper returns a formatted security violation banner to the tool, which passes it directly to the AI agent — including the blocked command, the timestamp, and instructions to contact an MQ administrator."

---

### Step 8 — Scenario 3: REST Discovery Without MQSC

> "The third scenario covers `discover_all_queue_managers`, which does not use MQSC at all. Because it only needs to list queue managers, it calls the REST API with a plain HTTP GET — no command string, no MQSC validation needed."

---

### Step 9 — Scenario 3: HTTP Method Validation

> "Instead of routing through `execute_mqsc_readonly`, the tool calls `validate_http_method` directly, passing `"GET"`. A note shows the rule: the only allowed HTTP method is GET; POST, PUT, DELETE, and PATCH are all blocked. Since GET is on the allowed list, the function returns `(True, "")`. The tool then calls `log_security_event` as an INFO record, and sends `GET /ibmmq/rest/v3/admin/qmgr/` to the REST API with Basic Auth. IBM MQ responds with a JSON object containing the list of queue managers, which the tool formats into a discovery report for the agent."

---

### Step 10 — Reading the Three Scenarios Together

> "Placing all three scenarios side by side tells the full story of the security model. Scenario 1 shows the normal operating path — validation passes, the audit log records an INFO event, IBM MQ is called, data flows back. Scenario 2 shows the protection path — validation fails, the audit log records a CRITICAL event, IBM MQ is never reached, a violation banner is returned. Scenario 3 shows the REST-only path for tools that do not use MQSC at all — they bypass the MQSC validator, go straight to the HTTP method check, and follow the same log-then-execute pattern. Together, these three paths cover every way the Read-Only server can be used, and in every case the audit log receives an entry before anything leaves the server."

---

## Quick Reference — Color Legend (both diagrams)

| Color | Meaning |
|-------|---------|
| Blue | AI Agent / MCP Client · Enterprise server tools · Enterprise→MQ arrows |
| Green | Enterprise MCP server container |
| Orange | Read-Only server container · Read-Only→MQ arrows · Audit logger |
| Red | Security enforcement layer components · Blocked command path |
| Purple | IBM MQ REST API · REST API→Queue Manager arrows |
