# MQ MCP Tools — `mqmcpserver_observe.py`

MCP tool server (Layer 2 of 4) that gives the AI chat platform the ability to answer **any** IBM MQ question from Observe using only 3 tools — regardless of how many metrics exist.

---

## Design Principle — Let the LLM Write the Query

The wrong instinct is to write one tool per metric:

```
❌ Bad: get_queue_depth, get_queue_throughput, get_channel_messages, get_fdc_count ...
        → 100s of metrics = 100s of tools
        → Cannot answer cross-metric questions
        → Every new metric needs a new tool deployment
```

The right approach is to give the LLM **knowledge** and a **query engine**:

```
✅ Good: discover_mq_context      → LLM learns what datasets/metrics exist
         execute_mq_opal_query    → LLM writes and runs any OPAL query it needs
         check_mq_observe_health  → verify the chain works

         3 tools cover all 100s of metrics now and in the future.
         Cross-metric questions work out of the box.
         New metrics in Observe need zero code changes.
```

### How the LLM uses these 3 tools

```
User: "Which queues on QM1 have old messages AND high depth?"

  Step 1: LLM calls discover_mq_context
          → learns: ibmmq_queue_oldest_message_age, ibmmq_queue_depth_perc exist
          → learns: datasets, dimensions (qmgr, queue), OPAL syntax

  Step 2: LLM writes OPAL query combining both metrics
          dataset "infra/metrics/mq/ibmmq_queue_depth_perc"
          | filter qmgr = "QM1"
          | filter ibmmq_queue_depth_perc > 50
          | join (
              dataset "infra/metrics/mq/ibmmq"
              | stats max(ibmmq_queue_oldest_message_age) by queue
            ) on queue

  Step 3: LLM calls execute_mq_opal_query with that query

  Step 4: LLM interprets results and answers the user in natural language
```

---

## Architecture

```
[1] Centralized Chat UI
         │  natural language question
         ▼
[2] MQ MCP Tools  ←  mqmcpserver_observe.py  (3 tools)
         │  HTTP GET /api/v1/mq/context
         │  HTTP GET /api/v1/mq/query?opal=...
         ▼
[3] MQ Context Provider  (mq-context-provider FastAPI service)
         │  via observability-common library
         ▼
[4] Observe MCP Server
    ├── generate_token       → health check auth validation
    ├── execute_opal_query   → runs LLM-generated OPAL queries
    ├── learn_observe_skill  → feeds metric schema to LLM
    └── discover_context     → feeds dataset list to LLM
         │
         ▼
     Observe Platform
     ├── infra/metrics/mq/ibmmq              (ID: 41007214)
     └── infra/metrics/mq/ibmmq_queue_depth_perc (ID: 41016986)
```

---

## Observe MQ Datasets

### `infra/metrics/mq/ibmmq` — ID: 41007214

| Category | Metric |
|---|---|
| Queue | `ibmmq_queue_expired_messages` |
| Queue | `ibmmq_queue_oldest_message_age` |
| Queue | `ibmmq_queue_average_queue_time_seconds` |
| Queue | `ibmmq_queue_uncommitted_messages` |
| Queue | `ibmmq_queue_mqput_persistent_message_count` |
| Queue | `ibmmq_queue_mqput_non_persistent_message_count` |
| Queue | `ibmmq_queue_destructive_mqget_persistent_message_count` |
| Queue | `ibmmq_queue_destructive_mqget_non_persistent_message_count` |
| Queue | `ibmmq_queue_mqget_browse_persistent_message_count` |
| Queue | `ibmmq_queue_mqget_browse_non_persistent_message_count` |
| QMgr | `ibmmq_qmgr_persistent_message_browse_count` |
| QMgr | `ibmmq_qmgr_persistent_message_browse_byte_count` |
| QMgr | `ibmmq_qmgr_persistent_message_mqput1_count` |
| QMgr | `ibmmq_qmgr_non_persistent_message_mqput1_count` |
| QMgr | `ibmmq_qmgr_mq_fdc_file_count` |
| Channel | `ibmmq_channel_messages` |
| Topic | `ibmmq_topic_messages_published` |
| + 100s more | discovered at runtime via `discover_mq_context` |

### `infra/metrics/mq/ibmmq_queue_depth_perc` — ID: 41016986

| Metric |
|---|
| `ibmmq_queue_depth_perc` |

---

## Installation

```bash
cd sample-mq-mcp
uv sync
```

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/), MQ Context Provider running.

## Configuration

| Variable | Description | Default |
|---|---|---|
| `MQ_CONTEXT_PROVIDER_URL` | Base URL of the MQ Context Provider service | `http://mq-context-provider:8000` |

```bash
export MQ_CONTEXT_PROVIDER_URL="http://mq-context-provider:8000"
uv run mqmcpserver_observe.py
```

---

## The 3 Tools

### `discover_mq_context`
**Always call this first.** Returns the full schema of MQ datasets, all metric names with descriptions, OPAL syntax guidance, and example queries. This is how the LLM knows what to query.

Calls Observe MCP tools: `discover_context` + `learn_observe_skill`

No arguments required.

---

### `execute_mq_opal_query`
Run any OPAL query against the MQ datasets. The LLM writes the query based on what it learned from `discover_mq_context`.

| Argument | Required | Description |
|---|---|---|
| `opal_query` | Yes | OPAL query string — written by the LLM |

**Example questions → LLM-generated queries:**

| User question | LLM writes this OPAL |
|---|---|
| "Queues over 80% full on QM1" | `dataset "infra/metrics/mq/ibmmq_queue_depth_perc" \| filter qmgr = "QM1" \| filter ibmmq_queue_depth_perc > 80` |
| "Stuck consumers on any queue manager" | `dataset "infra/metrics/mq/ibmmq" \| stats max(ibmmq_queue_oldest_message_age) by qmgr, queue \| top 10, max(ibmmq_queue_oldest_message_age) by queue` |
| "Any FDC errors?" | `dataset "infra/metrics/mq/ibmmq" \| filter ibmmq_qmgr_mq_fdc_file_count > 0 \| stats max(ibmmq_qmgr_mq_fdc_file_count) by qmgr` |
| "Channel throughput last hour" | `dataset "infra/metrics/mq/ibmmq" \| timechart 5m, sum(ibmmq_channel_messages) by channel` |
| "High depth AND old messages" | join query across both datasets |

---

### `check_mq_observe_health`
Verify the full connection chain is working. Calls Observe MCP `generate_token` to validate auth.

No arguments required.

---

## MQ Context Provider — Required Endpoints (Layer 3)

| Method | Path | Parameters | Observe MCP Tool |
|---|---|---|---|
| `GET` | `/health` | — | `generate_token` |
| `GET` | `/api/v1/mq/context` | — | `discover_context` + `learn_observe_skill` |
| `GET` | `/api/v1/mq/query` | `opal` | `execute_opal_query` |

Only **3 endpoints** needed. The MQ Context Provider passes the OPAL query straight through to Observe — no metric-specific logic required at Layer 3 either.

---

## Why Not More Tools?

| Approach | Tools needed | New metric = code change? | Cross-metric questions? |
|---|---|---|---|
| One tool per metric | 100s | Yes | No |
| LLM + query engine | 3 | No | Yes |

The LLM already understands IBM MQ. Give it the schema and a query engine — it will figure out the right query for any question.
