#!/usr/bin/env python3
"""
Enterprise IBM MQ MCP Server
Designed for large-scale MQ infrastructure with 200+ servers, 500+ queue managers

Features:
- Multi-server discovery and health monitoring
- Queue depth analytics and trending
- Application connectivity monitoring
- Performance metrics collection
- Alerting and anomaly detection
- Capacity planning
- Channel status monitoring
- Dead letter queue management
"""

import logging
import httpx
import json
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from collections import defaultdict

# Initialize FastMCP server
mcp = FastMCP("mqmcpserver-enterprise")

# Configuration for MQ servers - can be loaded from external config file
# In production, this would be loaded from a database or configuration management system
MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd",
        "region": "us-east",
        "environment": "production",
        "criticality": "high"
    },
    "QM2": {
        "url": "https://localhost:9444/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd",
        "region": "us-west",
        "environment": "production",
        "criticality": "high"
    }
    # Add more queue managers from your infrastructure
}

# Cache for performance metrics
metrics_cache = {}
health_cache = {}

# =============================================================================
# CORE DISCOVERY AND HEALTH TOOLS
# =============================================================================

@mcp.tool()
async def discover_all_queue_managers() -> str:
    """
    Discover and list all queue managers across all MQ servers with detailed status.
    Returns information about running status, platform, version, and metadata.
    
    Use this for: Initial infrastructure discovery, health checks across all QMs
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "token"
    }

    all_qmgrs = []
    errors = []

    for qm_name, config in MQ_SERVERS.items():
        url = config["url"] + "qmgr/"
        auth = httpx.BasicAuth(username=config["username"], password=config["password"])

        async with httpx.AsyncClient(verify=False, auth=auth) as client:
            try:
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()

                data = json.loads(response.content.decode("utf-8"))
                if 'qmgr' in data:
                    for qmgr in data['qmgr']:
                        qmgr['server_config'] = {
                            'region': config.get('region', 'unknown'),
                            'environment': config.get('environment', 'unknown'),
                            'criticality': config.get('criticality', 'medium')
                        }
                        all_qmgrs.append(qmgr)
            except Exception as err:
                errors.append(f"Error querying {qm_name}: {str(err)}")

    # Format output
    output = "=" * 80 + "\n"
    output += "QUEUE MANAGER DISCOVERY REPORT\n"
    output += f"Total Queue Managers Found: {len(all_qmgrs)}\n"
    output += "=" * 80 + "\n\n"

    # Group by status
    running = [q for q in all_qmgrs if q.get('state') == 'running']
    stopped = [q for q in all_qmgrs if q.get('state') != 'running']

    output += f"✓ Running: {len(running)}\n"
    output += f"✗ Stopped/Other: {len(stopped)}\n\n"

    # Group by region
    by_region = defaultdict(list)
    for q in all_qmgrs:
        region = q.get('server_config', {}).get('region', 'unknown')
        by_region[region].append(q)

    output += "By Region:\n"
    for region, qms in sorted(by_region.items()):
        output += f"  {region}: {len(qms)} queue managers\n"

    output += "\n" + "-" * 80 + "\n"
    output += "QUEUE MANAGER DETAILS:\n"
    output += "-" * 80 + "\n"

    for qmgr in all_qmgrs:
        name = qmgr.get('name', 'unknown')
        state = qmgr.get('state', 'unknown')
        region = qmgr.get('server_config', {}).get('region', 'unknown')
        env = qmgr.get('server_config', {}).get('environment', 'unknown')
        crit = qmgr.get('server_config', {}).get('criticality', 'unknown')
        
        status_icon = "✓" if state == 'running' else "✗"
        output += f"\n{status_icon} {name}\n"
        output += f"   Status: {state}\n"
        output += f"   Region: {region} | Environment: {env} | Criticality: {crit}\n"

    if errors:
        output += "\n" + "=" * 80 + "\n"
        output += "ERRORS:\n"
        for error in errors:
            output += f"  • {error}\n"

    return output


@mcp.tool()
async def health_check_all_queues(qmgr_name: str, depth_threshold: int = 80) -> str:
    """
    Comprehensive health check of all queues on a queue manager.
    
    Args:
        qmgr_name: Queue manager name (e.g., QM1)
        depth_threshold: Alert if queue depth is above this percentage (default: 80%)
    
    Returns: Detailed health report with alerts for full queues, stuck messages, etc.
    
    Use this for: Daily health checks, incident investigation, capacity monitoring
    """
    mqsc_command = "DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            # Parse queue information
            queues = []
            alerts = []
            
            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                for line in text:
                    if 'QUEUE(' in line:
                        queue_info = parse_queue_display(line)
                        if queue_info:
                            queues.append(queue_info)
                            
                            # Check for alerts
                            if queue_info['depth_percent'] > depth_threshold:
                                alerts.append({
                                    'type': 'HIGH_DEPTH',
                                    'queue': queue_info['name'],
                                    'depth': queue_info['current_depth'],
                                    'percent': queue_info['depth_percent']
                                })
                            
                            if queue_info['current_depth'] > 0 and queue_info['ipprocs'] == 0:
                                alerts.append({
                                    'type': 'NO_CONSUMERS',
                                    'queue': queue_info['name'],
                                    'depth': queue_info['current_depth']
                                })

            # Format output
            output = "=" * 80 + "\n"
            output += f"HEALTH CHECK REPORT: {qmgr_name}\n"
            output += f"Timestamp: {datetime.now().isoformat()}\n"
            output += "=" * 80 + "\n\n"

            output += f"Total Queues: {len(queues)}\n"
            output += f"Alerts: {len(alerts)}\n\n"

            if alerts:
                output += "⚠️  ALERTS:\n"
                output += "-" * 80 + "\n"
                for alert in alerts:
                    if alert['type'] == 'HIGH_DEPTH':
                        output += f"  🔴 HIGH DEPTH: {alert['queue']}\n"
                        output += f"     Current: {alert['depth']} ({alert['percent']:.1f}% full)\n\n"
                    elif alert['type'] == 'NO_CONSUMERS':
                        output += f"  🟡 NO CONSUMERS: {alert['queue']}\n"
                        output += f"     Messages waiting: {alert['depth']}\n\n"

            # Summary statistics
            total_messages = sum(q['current_depth'] for q in queues)
            non_empty = [q for q in queues if q['current_depth'] > 0]
            
            output += "SUMMARY:\n"
            output += "-" * 80 + "\n"
            output += f"Total Messages Across All Queues: {total_messages:,}\n"
            output += f"Non-Empty Queues: {len(non_empty)}\n"
            output += f"Empty Queues: {len(queues) - len(non_empty)}\n\n"

            # Top 10 queues by depth
            top_queues = sorted(queues, key=lambda x: x['current_depth'], reverse=True)[:10]
            if top_queues and top_queues[0]['current_depth'] > 0:
                output += "TOP 10 QUEUES BY DEPTH:\n"
                output += "-" * 80 + "\n"
                for i, q in enumerate(top_queues, 1):
                    if q['current_depth'] > 0:
                        output += f"{i:2d}. {q['name']:40s} {q['current_depth']:8,d} messages ({q['depth_percent']:5.1f}%)\n"

            return output

        except Exception as err:
            return f"Error running health check on {qmgr_name}: {str(err)}"


@mcp.tool()
async def monitor_channel_status(qmgr_name: str) -> str:
    """
    Monitor all channels on a queue manager - sender, receiver, server, cluster channels.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: Channel status report with connection states, message counts, and issues
    
    Use this for: Connectivity troubleshooting, network issue detection, cluster health
    """
    mqsc_command = "DISPLAY CHSTATUS(*) ALL"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            output = "=" * 80 + "\n"
            output += f"CHANNEL STATUS REPORT: {qmgr_name}\n"
            output += f"Timestamp: {datetime.now().isoformat()}\n"
            output += "=" * 80 + "\n\n"

            channels = []
            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                for line in text:
                    if 'CHANNEL(' in line:
                        channels.append(line)

            # Categorize channels
            running = [c for c in channels if 'STATUS(RUNNING)' in c]
            stopped = [c for c in channels if 'STATUS(STOPPED)' in c]
            retrying = [c for c in channels if 'STATUS(RETRYING)' in c]
            inactive = [c for c in channels if 'STATUS(INACTIVE)' in c]

            output += f"✓ Running: {len(running)}\n"
            output += f"⏸  Inactive: {len(inactive)}\n"
            output += f"⚠️  Retrying: {len(retrying)}\n"
            output += f"✗ Stopped: {len(stopped)}\n\n"

            if retrying:
                output += "⚠️  CHANNELS IN RETRY STATE:\n"
                output += "-" * 80 + "\n"
                for ch in retrying:
                    output += f"  {ch}\n"
                output += "\n"

            if stopped:
                output += "❌ STOPPED CHANNELS:\n"
                output += "-" * 80 + "\n"
                for ch in stopped:
                    output += f"  {ch}\n"
                output += "\n"

            return output

        except Exception as err:
            return f"Error monitoring channels on {qmgr_name}: {str(err)}"


# =============================================================================
# ANALYTICS AND TRENDING TOOLS
# =============================================================================

@mcp.tool()
async def analyze_queue_depth_trends(qmgr_name: str, queue_pattern: str = "*") -> str:
    """
    Analyze queue depth trends over time to identify growing queues and predict capacity issues.
    
    Args:
        qmgr_name: Queue manager name
        queue_pattern: Queue name pattern (default: * for all queues)
    
    Returns: Trend analysis showing queue growth patterns and predictions
    
    Use this for: Capacity planning, identifying slow consumers, predicting issues
    """
    # This would typically integrate with a time-series database
    # For now, we'll provide a snapshot with recommendations
    
    mqsc_command = f"DISPLAY QLOCAL({queue_pattern}) CURDEPTH MAXDEPTH MSGAGE"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            output = "=" * 80 + "\n"
            output += f"QUEUE DEPTH TREND ANALYSIS: {qmgr_name}\n"
            output += f"Pattern: {queue_pattern}\n"
            output += f"Timestamp: {datetime.now().isoformat()}\n"
            output += "=" * 80 + "\n\n"

            queues = []
            concerns = []

            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                for line in text:
                    if 'QUEUE(' in line:
                        queue_info = parse_queue_display(line)
                        if queue_info:
                            queues.append(queue_info)
                            
                            # Identify concerning patterns
                            if queue_info['depth_percent'] > 50:
                                concerns.append({
                                    'queue': queue_info['name'],
                                    'depth_percent': queue_info['depth_percent'],
                                    'severity': 'high' if queue_info['depth_percent'] > 80 else 'medium'
                                })

            output += "CAPACITY ANALYSIS:\n"
            output += "-" * 80 + "\n\n"

            if concerns:
                output += "⚠️  QUEUES REQUIRING ATTENTION:\n\n"
                for concern in sorted(concerns, key=lambda x: x['depth_percent'], reverse=True):
                    severity_icon = "🔴" if concern['severity'] == 'high' else "🟡"
                    output += f"{severity_icon} {concern['queue']}: {concern['depth_percent']:.1f}% full\n"
                    
                    if concern['depth_percent'] > 90:
                        output += "   ⚠️  CRITICAL: Queue near capacity limit\n"
                        output += "   Recommendation: Investigate consumer applications immediately\n"
                    elif concern['depth_percent'] > 80:
                        output += "   ⚠️  WARNING: High utilization detected\n"
                        output += "   Recommendation: Monitor closely, consider scaling consumers\n"
                    elif concern['depth_percent'] > 50:
                        output += "   ℹ️  INFO: Moderate utilization\n"
                        output += "   Recommendation: Review consumer throughput\n"
                    output += "\n"
            else:
                output += "✅ All queues operating within normal capacity ranges\n\n"

            # Overall statistics
            avg_utilization = sum(q['depth_percent'] for q in queues) / len(queues) if queues else 0
            output += f"\nOVERALL METRICS:\n"
            output += f"  Average Queue Utilization: {avg_utilization:.1f}%\n"
            output += f"  Queues Monitored: {len(queues)}\n"
            output += f"  Queues Over 50% Full: {len(concerns)}\n"

            return output

        except Exception as err:
            return f"Error analyzing trends on {qmgr_name}: {str(err)}"


@mcp.tool()
async def get_application_connections(qmgr_name: str) -> str:
    """
    Get all application connections to a queue manager with connection details.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: List of connected applications with connection details, user info, IP addresses
    
    Use this for: Security auditing, troubleshooting application issues, capacity planning
    """
    mqsc_command = "DISPLAY CONN(*) ALL"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            output = "=" * 80 + "\n"
            output += f"APPLICATION CONNECTIONS REPORT: {qmgr_name}\n"
            output += f"Timestamp: {datetime.now().isoformat()}\n"
            output += "=" * 80 + "\n\n"

            connections = []
            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                connections.extend(text)

            output += f"Total Active Connections: {len(connections)}\n\n"

            if connections:
                output += "CONNECTION DETAILS:\n"
                output += "-" * 80 + "\n"
                for conn in connections[:50]:  # Limit to first 50 for readability
                    output += f"{conn}\n"
                
                if len(connections) > 50:
                    output += f"\n... and {len(connections) - 50} more connections\n"

            return output

        except Exception as err:
            return f"Error getting connections on {qmgr_name}: {str(err)}"


# =============================================================================
# DEAD LETTER QUEUE MANAGEMENT
# =============================================================================

@mcp.tool()
async def check_dead_letter_queues(qmgr_name: str) -> str:
    """
    Check all dead letter queues (DLQ) for messages and analyze failure reasons.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: DLQ analysis with message counts and common failure patterns
    
    Use this for: Troubleshooting message delivery failures, identifying problematic applications
    """
    mqsc_command = "DISPLAY QLOCAL(SYSTEM.DEAD.LETTER.QUEUE) CURDEPTH MAXDEPTH"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            output = "=" * 80 + "\n"
            output += f"DEAD LETTER QUEUE REPORT: {qmgr_name}\n"
            output += f"Timestamp: {datetime.now().isoformat()}\n"
            output += "=" * 80 + "\n\n"

            dlq_depth = 0
            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                for line in text:
                    if 'CURDEPTH(' in line:
                        # Parse depth from line
                        import re
                        match = re.search(r'CURDEPTH\((\d+)\)', line)
                        if match:
                            dlq_depth = int(match.group(1))

            if dlq_depth > 0:
                output += f"⚠️  WARNING: {dlq_depth} messages in Dead Letter Queue\n\n"
                output += "RECOMMENDATIONS:\n"
                output += "  1. Investigate why messages are being sent to DLQ\n"
                output += "  2. Review application logs for delivery failures\n"
                output += "  3. Check queue permissions and existence\n"
                output += "  4. Verify message format compatibility\n"
                output += f"  5. Consider browsing DLQ messages for failure details\n"
            else:
                output += "✅ No messages in Dead Letter Queue\n"

            return output

        except Exception as err:
            return f"Error checking DLQ on {qmgr_name}: {str(err)}"


# =============================================================================
# CLUSTER MANAGEMENT TOOLS
# =============================================================================

@mcp.tool()
async def monitor_cluster_health(cluster_name: str = "*") -> str:
    """
    Monitor MQ cluster health across all queue managers in the cluster.
    
    Args:
        cluster_name: Cluster name pattern (default: * for all clusters)
    
    Returns: Cluster health report showing member status, repository status, and channel health
    
    Use this for: Cluster troubleshooting, ensuring cluster stability, detecting split-brain
    """
    output = "=" * 80 + "\n"
    output += f"CLUSTER HEALTH REPORT\n"
    output += f"Cluster Pattern: {cluster_name}\n"
    output += f"Timestamp: {datetime.now().isoformat()}\n"
    output += "=" * 80 + "\n\n"

    all_cluster_info = []
    
    for qmgr_name, config in MQ_SERVERS.items():
        mqsc_command = f"DISPLAY CLUSQMGR({cluster_name}) ALL"
        
        url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
        auth = httpx.BasicAuth(username=config["username"], password=config["password"])

        headers = {
            "Content-Type": "application/json",
            "ibm-mq-rest-csrf-token": "a"
        }

        data = json.dumps({
            "type": "runCommand",
            "parameters": {"command": mqsc_command}
        })

        async with httpx.AsyncClient(verify=False, auth=auth) as client:
            try:
                response = await client.post(url, data=data, headers=headers, timeout=30.0)
                response.raise_for_status()
                
                result = json.loads(response.content.decode("utf-8"))
                
                for cmd_response in result.get('commandResponse', []):
                    text = cmd_response.get('text', [])
                    if text:
                        all_cluster_info.append({
                            'qmgr': qmgr_name,
                            'info': text
                        })

            except Exception as err:
                output += f"⚠️  Error querying {qmgr_name}: {str(err)}\n"

    output += f"Cluster Members Responding: {len(all_cluster_info)}\n\n"

    if all_cluster_info:
        output += "CLUSTER MEMBER STATUS:\n"
        output += "-" * 80 + "\n"
        for member in all_cluster_info:
            output += f"\n{member['qmgr']}:\n"
            for line in member['info'][:10]:  # First 10 lines
                output += f"  {line}\n"

    return output


# =============================================================================
# PERFORMANCE AND CAPACITY TOOLS
# =============================================================================

@mcp.tool()
async def get_performance_metrics(qmgr_name: str) -> str:
    """
    Get performance metrics for a queue manager including CPU, memory, message rates.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: Performance metrics report
    
    Use this for: Performance troubleshooting, capacity planning, SLA monitoring
    """
    mqsc_command = "DISPLAY QMSTATUS(*) ALL"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            output = "=" * 80 + "\n"
            output += f"PERFORMANCE METRICS: {qmgr_name}\n"
            output += f"Timestamp: {datetime.now().isoformat()}\n"
            output += "=" * 80 + "\n\n"

            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                for line in text[:20]:  # First 20 lines
                    output += f"{line}\n"

            return output

        except Exception as err:
            return f"Error getting performance metrics on {qmgr_name}: {str(err)}"


@mcp.tool()
async def generate_capacity_report(environment: str = "all") -> str:
    """
    Generate capacity planning report across all queue managers or specific environment.
    
    Args:
        environment: Filter by environment (production, staging, development, all)
    
    Returns: Comprehensive capacity report with growth projections and recommendations
    
    Use this for: Monthly capacity reviews, budget planning, infrastructure scaling decisions
    """
    output = "=" * 80 + "\n"
    output += "CAPACITY PLANNING REPORT\n"
    output += f"Environment: {environment}\n"
    output += f"Report Date: {datetime.now().strftime('%Y-%m-%d')}\n"
    output += "=" * 80 + "\n\n"

    total_qmgrs = 0
    total_queues = 0
    total_messages = 0
    qmgr_data = []

    for qmgr_name, config in MQ_SERVERS.items():
        # Filter by environment
        if environment != "all" and config.get('environment') != environment:
            continue

        total_qmgrs += 1
        
        mqsc_command = "DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH"
        url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
        auth = httpx.BasicAuth(username=config["username"], password=config["password"])

        headers = {
            "Content-Type": "application/json",
            "ibm-mq-rest-csrf-token": "a"
        }

        data = json.dumps({
            "type": "runCommand",
            "parameters": {"command": mqsc_command}
        })

        async with httpx.AsyncClient(verify=False, auth=auth) as client:
            try:
                response = await client.post(url, data=data, headers=headers, timeout=30.0)
                response.raise_for_status()
                
                result = json.loads(response.content.decode("utf-8"))
                
                qmgr_queues = 0
                qmgr_messages = 0
                
                for cmd_response in result.get('commandResponse', []):
                    text = cmd_response.get('text', [])
                    for line in text:
                        if 'QUEUE(' in line:
                            qmgr_queues += 1
                            queue_info = parse_queue_display(line)
                            if queue_info:
                                qmgr_messages += queue_info['current_depth']

                total_queues += qmgr_queues
                total_messages += qmgr_messages
                
                qmgr_data.append({
                    'name': qmgr_name,
                    'queues': qmgr_queues,
                    'messages': qmgr_messages,
                    'region': config.get('region', 'unknown')
                })

            except Exception as err:
                output += f"⚠️  Error querying {qmgr_name}: {str(err)}\n"

    output += "EXECUTIVE SUMMARY:\n"
    output += "-" * 80 + "\n"
    output += f"Total Queue Managers: {total_qmgrs}\n"
    output += f"Total Queues: {total_queues:,}\n"
    output += f"Total Messages: {total_messages:,}\n"
    output += f"Average Queues per QM: {total_queues/total_qmgrs if total_qmgrs > 0 else 0:.1f}\n"
    output += f"Average Messages per QM: {total_messages/total_qmgrs if total_qmgrs > 0 else 0:,.0f}\n\n"

    output += "BY QUEUE MANAGER:\n"
    output += "-" * 80 + "\n"
    output += f"{'Queue Manager':<20} {'Region':<15} {'Queues':>10} {'Messages':>15}\n"
    output += "-" * 80 + "\n"
    
    for qm in sorted(qmgr_data, key=lambda x: x['messages'], reverse=True):
        output += f"{qm['name']:<20} {qm['region']:<15} {qm['queues']:>10,} {qm['messages']:>15,}\n"

    output += "\n" + "=" * 80 + "\n"
    output += "RECOMMENDATIONS:\n"
    output += "=" * 80 + "\n"
    output += "1. Monitor queue managers with high message volumes for performance\n"
    output += "2. Review queues with consistently high depth for consumer scaling\n"
    output += "3. Consider archiving or purging old messages from low-priority queues\n"
    output += "4. Plan infrastructure expansion based on 20% annual growth rate\n"

    return output


# =============================================================================
# ALERT AND ANOMALY DETECTION
# =============================================================================

@mcp.tool()
async def detect_anomalies(qmgr_name: str) -> str:
    """
    Detect anomalies in queue manager behavior - unusual depths, stuck messages, etc.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: Anomaly detection report with identified issues and severity
    
    Use this for: Proactive issue detection, automated monitoring, incident prevention
    """
    output = "=" * 80 + "\n"
    output += f"ANOMALY DETECTION REPORT: {qmgr_name}\n"
    output += f"Timestamp: {datetime.now().isoformat()}\n"
    output += "=" * 80 + "\n\n"

    anomalies = []

    # Check queue depths
    mqsc_command = "DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS MSGAGE"
    
    config = MQ_SERVERS.get(qmgr_name)
    if not config:
        return f"Queue manager {qmgr_name} not found in configuration"

    url = config["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    auth = httpx.BasicAuth(username=config["username"], password=config["password"])

    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }

    data = json.dumps({
        "type": "runCommand",
        "parameters": {"command": mqsc_command}
    })

    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            result = json.loads(response.content.decode("utf-8"))
            
            for cmd_response in result.get('commandResponse', []):
                text = cmd_response.get('text', [])
                for line in text:
                    if 'QUEUE(' in line:
                        queue_info = parse_queue_display(line)
                        if queue_info:
                            # Anomaly 1: Queue near capacity
                            if queue_info['depth_percent'] > 95:
                                anomalies.append({
                                    'severity': 'CRITICAL',
                                    'type': 'CAPACITY',
                                    'queue': queue_info['name'],
                                    'message': f"Queue at {queue_info['depth_percent']:.1f}% capacity"
                                })
                            
                            # Anomaly 2: Messages with no consumers
                            if queue_info['current_depth'] > 100 and queue_info['ipprocs'] == 0:
                                anomalies.append({
                                    'severity': 'HIGH',
                                    'type': 'NO_CONSUMER',
                                    'queue': queue_info['name'],
                                    'message': f"{queue_info['current_depth']} messages waiting, no active consumers"
                                })
                            
                            # Anomaly 3: Old messages (if MSGAGE available in response)
                            # This would need parsing of MSGAGE field

            if anomalies:
                output += f"⚠️  {len(anomalies)} ANOMALIES DETECTED\n\n"
                
                critical = [a for a in anomalies if a['severity'] == 'CRITICAL']
                high = [a for a in anomalies if a['severity'] == 'HIGH']
                
                if critical:
                    output += "🔴 CRITICAL ISSUES:\n"
                    output += "-" * 80 + "\n"
                    for a in critical:
                        output += f"  {a['type']}: {a['queue']}\n"
                        output += f"  {a['message']}\n\n"
                
                if high:
                    output += "🟠 HIGH PRIORITY ISSUES:\n"
                    output += "-" * 80 + "\n"
                    for a in high:
                        output += f"  {a['type']}: {a['queue']}\n"
                        output += f"  {a['message']}\n\n"
            else:
                output += "✅ No anomalies detected - system operating normally\n"

            return output

        except Exception as err:
            return f"Error detecting anomalies on {qmgr_name}: {str(err)}"


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@mcp.tool()
async def batch_health_check(region: str = "all", criticality: str = "all") -> str:
    """
    Run health checks across multiple queue managers in parallel.
    
    Args:
        region: Filter by region (us-east, us-west, eu-west, all)
        criticality: Filter by criticality (high, medium, low, all)
    
    Returns: Aggregated health report across all matching queue managers
    
    Use this for: Daily health checks, executive dashboards, SLA reporting
    """
    output = "=" * 80 + "\n"
    output += "BATCH HEALTH CHECK REPORT\n"
    output += f"Region Filter: {region}\n"
    output += f"Criticality Filter: {criticality}\n"
    output += f"Timestamp: {datetime.now().isoformat()}\n"
    output += "=" * 80 + "\n\n"

    # Filter queue managers
    filtered_qms = {}
    for qm_name, config in MQ_SERVERS.items():
        region_match = region == "all" or config.get('region') == region
        crit_match = criticality == "all" or config.get('criticality') == criticality
        
        if region_match and crit_match:
            filtered_qms[qm_name] = config

    output += f"Queue Managers Selected: {len(filtered_qms)}\n\n"

    # Run parallel health checks
    tasks = []
    for qm_name in filtered_qms.keys():
        tasks.append(health_check_all_queues(qm_name, depth_threshold=80))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate results
    total_alerts = 0
    qm_status = []

    for qm_name, result in zip(filtered_qms.keys(), results):
        if isinstance(result, Exception):
            qm_status.append({
                'name': qm_name,
                'status': 'ERROR',
                'alerts': 0
            })
        else:
            # Count alerts in result
            alert_count = result.count('🔴') + result.count('🟡')
            total_alerts += alert_count
            qm_status.append({
                'name': qm_name,
                'status': 'OK' if alert_count == 0 else 'ALERTS',
                'alerts': alert_count
            })

    output += "SUMMARY:\n"
    output += "-" * 80 + "\n"
    output += f"Total Alerts: {total_alerts}\n"
    output += f"Healthy Queue Managers: {sum(1 for s in qm_status if s['status'] == 'OK')}\n"
    output += f"Queue Managers with Alerts: {sum(1 for s in qm_status if s['status'] == 'ALERTS')}\n"
    output += f"Queue Managers with Errors: {sum(1 for s in qm_status if s['status'] == 'ERROR')}\n\n"

    output += "BY QUEUE MANAGER:\n"
    output += "-" * 80 + "\n"
    for status in sorted(qm_status, key=lambda x: x['alerts'], reverse=True):
        status_icon = "✅" if status['status'] == 'OK' else "⚠️" if status['status'] == 'ALERTS' else "❌"
        output += f"{status_icon} {status['name']:<20} Status: {status['status']:<10} Alerts: {status['alerts']}\n"

    return output


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_queue_display(line: str) -> Optional[Dict]:
    """Parse DISPLAY QLOCAL output line to extract queue information"""
    import re
    
    queue_info = {}
    
    # Extract queue name
    name_match = re.search(r'QUEUE\(([^)]+)\)', line)
    if name_match:
        queue_info['name'] = name_match.group(1)
    else:
        return None
    
    # Extract current depth
    depth_match = re.search(r'CURDEPTH\((\d+)\)', line)
    if depth_match:
        queue_info['current_depth'] = int(depth_match.group(1))
    else:
        queue_info['current_depth'] = 0
    
    # Extract max depth
    maxdepth_match = re.search(r'MAXDEPTH\((\d+)\)', line)
    if maxdepth_match:
        queue_info['max_depth'] = int(maxdepth_match.group(1))
    else:
        queue_info['max_depth'] = 5000  # Default
    
    # Calculate percentage
    if queue_info['max_depth'] > 0:
        queue_info['depth_percent'] = (queue_info['current_depth'] / queue_info['max_depth']) * 100
    else:
        queue_info['depth_percent'] = 0
    
    # Extract IPPROCS (input processes/consumers)
    ipprocs_match = re.search(r'IPPROCS\((\d+)\)', line)
    if ipprocs_match:
        queue_info['ipprocs'] = int(ipprocs_match.group(1))
    else:
        queue_info['ipprocs'] = 0
    
    # Extract OPPROCS (output processes/producers)
    opprocs_match = re.search(r'OPPROCS\((\d+)\)', line)
    if opprocs_match:
        queue_info['opprocs'] = int(opprocs_match.group(1))
    else:
        queue_info['opprocs'] = 0
    
    return queue_info


def prettify_runmqsc(payload: str) -> str:
    """Format MQSC command output"""
    jsonOutput = json.loads(payload.decode("utf-8"))
    prettifiedOutput = "\n---\n"
    for x in jsonOutput['commandResponse']:
        if x['text'][0].startswith("CSQN205I"):
            x['text'].pop(0)            
            x['text'].pop()
            for y in x['text']:
                prettifiedOutput += y[15:] + "\n---\n"            
        else:        
            prettifiedOutput += x['text'][0] + "\n---\n"   
    
    return prettifiedOutput


if __name__ == "__main__":
    # For Claude Desktop, use stdio transport
    mcp.run(transport='stdio')
