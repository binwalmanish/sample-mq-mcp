#!/usr/bin/env python3
"""
IBM MQ MCP Tool (Layer 2 of 4)

Design principle:
    Do NOT write a tool per metric. Instead give the LLM:
      1. Knowledge of what datasets and metrics exist  (discover_mq_context)
      2. Ability to run any query it constructs        (execute_mq_opal_query)
      3. A health check                                (check_mq_observe_health)

    The LLM reads the user's question, chooses the right metrics,
    writes the OPAL query, and calls execute_mq_opal_query — covering
    all 100s of metrics without a single hard-coded tool per metric.

4-layer architecture:
    [1] Chat UI
         ↓  natural language question
    [2] MQ MCP Tools  ← THIS FILE  (3 tools only)
         ↓  HTTP REST
    [3] MQ Context Provider  (mq-context-provider FastAPI service)
         ↓  via observability-common
    [4] Observe MCP Server
         ├── generate_token       → used by health check
         ├── execute_opal_query   → used by execute_mq_opal_query
         ├── learn_observe_skill  → used by discover_mq_context
         └── discover_context     → used by discover_mq_context

Observe MQ Datasets:
    infra/metrics/mq/ibmmq              (ID: 41007214) — all MQ metrics
    infra/metrics/mq/ibmmq_queue_depth_perc (ID: 41016986) — queue depth %

Environment variable:
    MQ_CONTEXT_PROVIDER_URL  Base URL of mq-context-provider (default: http://mq-context-provider:8000)
"""

import os
import json

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mq-mcp-tools")

MQ_CONTEXT_PROVIDER_URL = os.getenv(
    "MQ_CONTEXT_PROVIDER_URL",
    "http://mq-context-provider:8000",
).rstrip("/")


async def _get(path: str, params: dict | None = None) -> dict:
    url = f"{MQ_CONTEXT_PROVIDER_URL}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()


def _fmt(data: dict | list) -> str:
    return json.dumps(data, indent=2)


def _handle_error(e: Exception, path: str) -> str:
    if isinstance(e, httpx.ConnectError):
        return (
            f"Cannot reach MQ Context Provider at {MQ_CONTEXT_PROVIDER_URL}{path}\n"
            "Check MQ_CONTEXT_PROVIDER_URL."
        )
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 503:
            return "MQ Context Provider unavailable (503) — Observe MCP may be down."
        if e.response.status_code == 401:
            return "Unauthorized (401) — check OBSERVABILITY_MCP_TOKEN in mq-context-provider."
        return f"MQ Context Provider returned {e.response.status_code}: {e.response.text}"
    return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Tool 1 — Context discovery
# Call this FIRST so the LLM knows what datasets and metrics exist before
# writing any OPAL query. Combines discover_context + learn_observe_skill.
# ---------------------------------------------------------------------------

@mcp.tool()
async def discover_mq_context() -> str:
    """
    Discover all IBM MQ datasets, metrics, and query capabilities available in Observe.

    ALWAYS call this tool first before execute_mq_opal_query so you know:
      - Which datasets exist and their IDs
      - What metric names are available (there are 100s)
      - How to structure OPAL queries for MQ data
      - Which dimensions (qmgr, queue, channel) can be used to filter

    Returns:
        Full schema of MQ datasets, all available metric names with descriptions,
        OPAL query syntax guidance, and example queries.
    """
    try:
        data = await _get("/api/v1/mq/context")
        return _fmt(data)
    except Exception as e:
        return _handle_error(e, "/api/v1/mq/context")


# ---------------------------------------------------------------------------
# Tool 2 — Query execution
# The LLM writes the OPAL query based on context from discover_mq_context,
# then calls this tool. Covers every metric, every combination, every filter.
# ---------------------------------------------------------------------------

@mcp.tool()
async def execute_mq_opal_query(opal_query: str) -> str:
    """
    Execute an OPAL query against the IBM MQ datasets in Observe and return results.

    Use this after calling discover_mq_context to understand what is available.
    Write the OPAL query yourself based on the user's question — do not hardcode queries.

    OPAL query syntax:
        dataset "<dataset_name>"
        | filter <dimension> = "<value>"     -- filter by qmgr, queue, channel, etc.
        | timechart <interval>,              -- time series (e.g. 1m, 5m, 1h)
            <aggregation>(<metric>)          -- sum(), max(), avg(), min()
        | stats <aggregation>(<metric>)      -- point-in-time aggregation
            by <dimension>
        | top <n>, <aggregation>(<metric>)   -- top N results
            by <dimension>
        | filter <metric> > <value>          -- threshold filter on a metric

    Available datasets:
        "infra/metrics/mq/ibmmq"                  ID: 41007214  (all MQ metrics)
        "infra/metrics/mq/ibmmq_queue_depth_perc" ID: 41016986  (queue depth %)

    Example queries — adapt these to the user's actual question:

        # Queues over 80% full on QM1
        dataset "infra/metrics/mq/ibmmq_queue_depth_perc"
        | filter qmgr = "QM1"
        | stats max(ibmmq_queue_depth_perc) by queue
        | filter ibmmq_queue_depth_perc > 80

        # Put and get throughput over last hour
        dataset "infra/metrics/mq/ibmmq"
        | filter qmgr = "QM1"
        | filter queue = "APP.INPUT.Q"
        | timechart 5m,
            sum(ibmmq_queue_mqput_persistent_message_count),
            sum(ibmmq_queue_destructive_mqget_persistent_message_count)

        # Queues with old messages (stuck consumer detection)
        dataset "infra/metrics/mq/ibmmq"
        | filter qmgr = "QM1"
        | stats max(ibmmq_queue_oldest_message_age) by queue
        | top 10, max(ibmmq_queue_oldest_message_age) by queue

        # Queues with uncommitted transactions
        dataset "infra/metrics/mq/ibmmq"
        | filter ibmmq_queue_uncommitted_messages > 0
        | stats max(ibmmq_queue_uncommitted_messages) by qmgr, queue

        # FDC errors across all queue managers
        dataset "infra/metrics/mq/ibmmq"
        | stats max(ibmmq_qmgr_mq_fdc_file_count) by qmgr
        | filter ibmmq_qmgr_mq_fdc_file_count > 0

        # Channel throughput
        dataset "infra/metrics/mq/ibmmq"
        | filter qmgr = "QM1"
        | timechart 5m, sum(ibmmq_channel_messages) by channel

        # Topic publish rate
        dataset "infra/metrics/mq/ibmmq"
        | timechart 5m, sum(ibmmq_topic_messages_published) by qmgr

        # Combined: high depth + old messages (multi-metric analysis)
        dataset "infra/metrics/mq/ibmmq_queue_depth_perc"
        | filter qmgr = "QM1"
        | filter ibmmq_queue_depth_perc > 50
        | join (
            dataset "infra/metrics/mq/ibmmq"
            | stats max(ibmmq_queue_oldest_message_age) by queue
          ) on queue

    Args:
        opal_query: The complete OPAL query to run. Write this based on the
                    user's question and the schema from discover_mq_context.

    Returns:
        Query results from Observe. Interpret and summarise these for the user.
    """
    try:
        data = await _get("/api/v1/mq/query", {"opal": opal_query})
        return _fmt(data)
    except Exception as e:
        return _handle_error(e, "/api/v1/mq/query")


# ---------------------------------------------------------------------------
# Tool 3 — Health check
# Verifies the full chain is working before the user tries any query.
# Uses generate_token internally to validate Observe auth.
# ---------------------------------------------------------------------------

@mcp.tool()
async def check_mq_observe_health() -> str:
    """
    Verify the full connection chain: MQ MCP Tools → MQ Context Provider → Observe MCP → Observe.
    Call this if queries are failing or to confirm the integration is working.

    Returns:
        Health status of each layer: context provider reachability,
        Observe MCP connectivity, and token validity.
    """
    try:
        data = await _get("/health")
        return _fmt(data)
    except Exception as e:
        return _handle_error(e, "/health")


if __name__ == "__main__":
    print(f"MQ MCP Tools — MQ Context Provider: {MQ_CONTEXT_PROVIDER_URL}")
    print("Set MQ_CONTEXT_PROVIDER_URL to override.")
    print()
    mcp.run(transport='stdio')
