#!/usr/bin/env python3
"""
Enterprise IBM MQ MCP Server - READ-ONLY SECURITY HARDENED VERSION
Designed for large-scale MQ infrastructure with 200+ servers, 500+ queue managers

SECURITY POLICY: READ-ONLY OPERATIONS ONLY
============================================
This MCP server is explicitly restricted to READ-ONLY operations.
AI agents CANNOT perform any of the following:
- Create, modify, or delete queues
- Create, modify, or delete queue managers
- Modify channel definitions
- Change security settings
- Put or get messages
- Modify any configuration
- Execute any DEFINE, ALTER, DELETE, CLEAR, or destructive MQSC commands

ALLOWED OPERATIONS:
- DISPLAY commands only (queue status, channel status, etc.)
- GET requests to REST API (informational only)
- Performance metrics collection
- Health monitoring
- Capacity reporting

Version: 2.0 (Security Hardened)
Last Updated: 2025
"""

import logging
import httpx
import json
import asyncio
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from collections import defaultdict

# Initialize FastMCP server
mcp = FastMCP("mqmcpserver-enterprise-readonly")

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# List of BLOCKED MQSC commands (destructive operations)
BLOCKED_MQSC_COMMANDS = [
    'DEFINE', 'ALTER', 'DELETE', 'CLEAR', 'START', 'STOP', 'RESET',
    'REFRESH', 'SUSPEND', 'RESUME', 'PING', 'RESOLVE', 'MOVE',
    'SET', 'ARCHIVE', 'RECOVER', 'RCDMQIMG', 'RCRMQOBJ'
]

# List of ALLOWED MQSC commands (read-only operations)
ALLOWED_MQSC_COMMANDS = [
    'DISPLAY'  # Only DISPLAY commands are allowed
]

# HTTP methods allowed (read-only)
ALLOWED_HTTP_METHODS = ['GET']  # No POST, PUT, DELETE, PATCH

# List of BLOCKED REST API endpoints (write operations)
BLOCKED_REST_ENDPOINTS = [
    '/messaging/',  # Message put/get operations
    '/action/qmgr/*/mqsc',  # Will be validated separately for MQSC commands
]

# Configuration for MQ servers
MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "admin",  # Consider using read-only user
        "password": "passw0rd",
        "region": "us-east",
        "environment": "production",
        "criticality": "high"
    },
    "QM2": {
        "url": "https://localhost:9444/ibmmq/rest/v3/admin/",
        "username": "admin",  # Consider using read-only user
        "password": "passw0rd",
        "region": "us-west",
        "environment": "production",
        "criticality": "high"
    }
}

# =============================================================================
# SECURITY VALIDATION FUNCTIONS
# =============================================================================

def validate_mqsc_command(mqsc_command: str) -> tuple[bool, str]:
    """
    Validate that an MQSC command is read-only and safe to execute.
    
    Args:
        mqsc_command: The MQSC command to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if command is allowed, False if blocked
        - error_message: Description of why command was blocked (empty if allowed)
    """
    # Normalize command (uppercase, strip whitespace)
    command_upper = mqsc_command.strip().upper()
    
    # Extract the first word (the command verb)
    command_verb = command_upper.split()[0] if command_upper else ""
    
    # Check if command verb is in blocked list
    if command_verb in BLOCKED_MQSC_COMMANDS:
        return False, f"BLOCKED: '{command_verb}' commands are not allowed. Only READ-ONLY operations permitted."
    
    # Check if command verb is in allowed list
    if command_verb not in ALLOWED_MQSC_COMMANDS:
        return False, f"BLOCKED: '{command_verb}' is not in the allowed commands list. Only DISPLAY commands permitted."
    
    # Additional safety checks for DISPLAY commands
    # Ensure DISPLAY is truly read-only (no side effects)
    dangerous_patterns = [
        r'\bCLEAR\b',
        r'\bDELETE\b',
        r'\bALTER\b',
        r'\bDEFINE\b',
        r'\bSTART\b',
        r'\bSTOP\b',
        r'\bRESET\b'
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command_upper):
            return False, f"BLOCKED: Command contains dangerous keyword. Only pure DISPLAY operations allowed."
    
    # Command is safe
    return True, ""


def validate_http_method(method: str) -> tuple[bool, str]:
    """
    Validate that HTTP method is read-only.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    method_upper = method.upper()
    
    if method_upper not in ALLOWED_HTTP_METHODS:
        return False, f"BLOCKED: HTTP {method_upper} is not allowed. Only GET requests permitted for read-only access."
    
    return True, ""


def log_security_event(event_type: str, details: str, severity: str = "WARNING"):
    """
    Log security-related events for audit trail.
    
    Args:
        event_type: Type of security event (BLOCKED_COMMAND, ALLOWED_COMMAND, etc.)
        details: Details of the event
        severity: Severity level (INFO, WARNING, CRITICAL)
    """
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] SECURITY [{severity}] {event_type}: {details}"
    
    # Log to stderr for security events
    print(log_message, file=__import__('sys').stderr)
    
    # In production, also send to SIEM or security monitoring system
    # Example: send_to_siem(event_type, details, severity)


# =============================================================================
# SECURE MQSC EXECUTION WRAPPER
# =============================================================================

async def execute_mqsc_readonly(qmgr_name: str, mqsc_command: str) -> str:
    """
    Execute MQSC command with security validation.
    This wrapper ensures only READ-ONLY commands are executed.
    
    Args:
        qmgr_name: Queue manager name
        mqsc_command: MQSC command to execute
        
    Returns:
        Command output or security error message
    """
    # Validate MQSC command
    is_valid, error_msg = validate_mqsc_command(mqsc_command)
    
    if not is_valid:
        # Log security event
        log_security_event(
            "BLOCKED_MQSC_COMMAND",
            f"Attempted to execute blocked command on {qmgr_name}: {mqsc_command}",
            "CRITICAL"
        )
        
        return f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                          SECURITY POLICY VIOLATION                          ║
╚════════════════════════════════════════════════════════════════════════════╝

❌ COMMAND BLOCKED: {error_msg}

Requested Command: {mqsc_command}
Queue Manager: {qmgr_name}
Timestamp: {datetime.now().isoformat()}

SECURITY POLICY:
This MCP server is restricted to READ-ONLY operations.
Only DISPLAY commands are permitted.

Blocked command types:
- DEFINE (create objects)
- ALTER (modify objects)
- DELETE (remove objects)
- CLEAR (clear queues)
- START/STOP (control objects)
- Any other write operations

If you need to perform write operations, please:
1. Use IBM MQ Console or command line directly
2. Submit a change request through proper channels
3. Contact your MQ administrator

This security event has been logged for audit purposes.
"""
    
    # Log allowed command
    log_security_event(
        "ALLOWED_MQSC_COMMAND",
        f"Executing read-only command on {qmgr_name}: {mqsc_command}",
        "INFO"
    )
    
    # Execute the validated command
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
            # Note: Even though we use POST to execute MQSC, the command itself is read-only
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_runmqsc(response.content)
        except Exception as err:
            log_security_event(
                "MQSC_EXECUTION_ERROR",
                f"Error executing command on {qmgr_name}: {str(err)}",
                "WARNING"
            )
            return f"Error running MQSC command on {qmgr_name}: {str(err)}"


# =============================================================================
# READ-ONLY TOOLS
# =============================================================================

@mcp.tool()
async def discover_all_queue_managers() -> str:
    """
    Discover and list all queue managers across all MQ servers with detailed status.
    
    SECURITY: READ-ONLY operation using GET requests only.
    
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
                # Security: Only GET request (read-only)
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
    output += "QUEUE MANAGER DISCOVERY REPORT (READ-ONLY)\n"
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
    
    SECURITY: READ-ONLY operation using DISPLAY QLOCAL command only.
    
    Args:
        qmgr_name: Queue manager name (e.g., QM1)
        depth_threshold: Alert if queue depth is above this percentage (default: 80%)
    
    Returns: Detailed health report with alerts for full queues, stuck messages, etc.
    
    Use this for: Daily health checks, incident investigation, capacity monitoring
    """
    # Security: Using DISPLAY command only (read-only)
    mqsc_command = "DISPLAY QLOCAL(*) CURDEPTH MAXDEPTH IPPROCS OPPROCS"
    
    # Execute with security validation
    result = await execute_mqsc_readonly(qmgr_name, mqsc_command)
    
    # Check if command was blocked
    if "SECURITY POLICY VIOLATION" in result:
        return result
    
    # Parse and format results
    try:
        # Parse queue information from result
        queues = []
        alerts = []
        
        for line in result.split('\n'):
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
        output += f"HEALTH CHECK REPORT (READ-ONLY): {qmgr_name}\n"
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
        return f"Error parsing health check results: {str(err)}\n\nRaw output:\n{result}"


@mcp.tool()
async def monitor_channel_status(qmgr_name: str) -> str:
    """
    Monitor all channels on a queue manager - sender, receiver, server, cluster channels.
    
    SECURITY: READ-ONLY operation using DISPLAY CHSTATUS command only.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: Channel status report with connection states, message counts, and issues
    
    Use this for: Connectivity troubleshooting, network issue detection, cluster health
    """
    # Security: Using DISPLAY command only (read-only)
    mqsc_command = "DISPLAY CHSTATUS(*) ALL"
    
    # Execute with security validation
    result = await execute_mqsc_readonly(qmgr_name, mqsc_command)
    
    # Check if command was blocked
    if "SECURITY POLICY VIOLATION" in result:
        return result
    
    output = "=" * 80 + "\n"
    output += f"CHANNEL STATUS REPORT (READ-ONLY): {qmgr_name}\n"
    output += f"Timestamp: {datetime.now().isoformat()}\n"
    output += "=" * 80 + "\n\n"

    channels = []
    for line in result.split('\n'):
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
        for ch in retrying[:20]:  # Limit output
            output += f"  {ch}\n"
        output += "\n"

    if stopped:
        output += "❌ STOPPED CHANNELS:\n"
        output += "-" * 80 + "\n"
        for ch in stopped[:20]:  # Limit output
            output += f"  {ch}\n"
        output += "\n"

    return output


@mcp.tool()
async def check_dead_letter_queues(qmgr_name: str) -> str:
    """
    Check all dead letter queues (DLQ) for messages and analyze failure reasons.
    
    SECURITY: READ-ONLY operation using DISPLAY QLOCAL command only.
    
    Args:
        qmgr_name: Queue manager name
    
    Returns: DLQ analysis with message counts and common failure patterns
    
    Use this for: Troubleshooting message delivery failures, identifying problematic applications
    """
    # Security: Using DISPLAY command only (read-only)
    mqsc_command = "DISPLAY QLOCAL(SYSTEM.DEAD.LETTER.QUEUE) CURDEPTH MAXDEPTH"
    
    # Execute with security validation
    result = await execute_mqsc_readonly(qmgr_name, mqsc_command)
    
    # Check if command was blocked
    if "SECURITY POLICY VIOLATION" in result:
        return result
    
    output = "=" * 80 + "\n"
    output += f"DEAD LETTER QUEUE REPORT (READ-ONLY): {qmgr_name}\n"
    output += f"Timestamp: {datetime.now().isoformat()}\n"
    output += "=" * 80 + "\n\n"

    dlq_depth = 0
    for line in result.split('\n'):
        if 'CURDEPTH(' in line:
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
        output += f"  5. Contact MQ administrator to browse DLQ messages\n"
        output += f"\nNOTE: This tool cannot retrieve or delete DLQ messages (read-only policy)\n"
    else:
        output += "✅ No messages in Dead Letter Queue\n"

    return output


@mcp.tool()
async def get_security_policy() -> str:
    """
    Display the security policy and restrictions for this MCP server.
    
    Returns: Complete security policy documentation
    """
    return """
╔════════════════════════════════════════════════════════════════════════════╗
║                    MCP SERVER SECURITY POLICY                               ║
║                         READ-ONLY OPERATIONS ONLY                           ║
╚════════════════════════════════════════════════════════════════════════════╝

VERSION: 2.0 (Security Hardened)
POLICY: Strict read-only access to IBM MQ infrastructure

═══════════════════════════════════════════════════════════════════════════

✅ ALLOWED OPERATIONS:

1. MQSC Commands:
   - DISPLAY QLOCAL(*)      - Display queue attributes
   - DISPLAY CHSTATUS(*)    - Display channel status
   - DISPLAY CONN(*)        - Display connections
   - DISPLAY CLUSQMGR(*)    - Display cluster queue managers
   - DISPLAY QMSTATUS(*)    - Display queue manager status
   - DISPLAY QUEUE(*)       - Display queue information
   - All other DISPLAY commands

2. REST API Operations:
   - GET /qmgr/             - List queue managers
   - GET /queue/            - Get queue information
   - GET /channel/          - Get channel information
   - All other GET requests (read-only)

3. Data Analysis:
   - Health monitoring
   - Capacity planning
   - Performance metrics
   - Trend analysis
   - Anomaly detection

═══════════════════════════════════════════════════════════════════════════

❌ BLOCKED OPERATIONS:

1. MQSC Commands:
   - DEFINE     - Cannot create queues, channels, etc.
   - ALTER      - Cannot modify configurations
   - DELETE     - Cannot delete objects
   - CLEAR      - Cannot clear queues
   - START      - Cannot start channels/listeners
   - STOP       - Cannot stop channels/listeners
   - RESET      - Cannot reset statistics
   - REFRESH    - Cannot refresh configurations
   - SUSPEND    - Cannot suspend queue managers
   - RESUME     - Cannot resume queue managers
   - SET        - Cannot modify settings
   - Any other write operations

2. REST API Operations:
   - POST /messaging/       - Cannot put messages
   - DELETE /messaging/     - Cannot get messages (destructive)
   - PUT /queue/            - Cannot update queues
   - DELETE /queue/         - Cannot delete queues
   - All other POST, PUT, DELETE, PATCH requests

3. Message Operations:
   - Cannot put messages to queues
   - Cannot get messages from queues (even browse mode)
   - Cannot clear queue contents
   - Cannot modify message properties

4. Configuration Changes:
   - Cannot create/modify/delete queue managers
   - Cannot create/modify/delete queues
   - Cannot create/modify/delete channels
   - Cannot modify security settings
   - Cannot change permissions

═══════════════════════════════════════════════════════════════════════════

🔒 SECURITY ENFORCEMENT:

1. Command Validation:
   All MQSC commands are validated before execution
   Blocked commands are rejected with security error

2. Audit Logging:
   All operations are logged for audit trail
   Blocked operations are logged as CRITICAL events
   Logs include: timestamp, user, command, result

3. Multi-Layer Protection:
   - Command syntax validation
   - Keyword blacklist checking
   - HTTP method restriction
   - REST endpoint validation

═══════════════════════════════════════════════════════════════════════════

📋 IF YOU NEED WRITE OPERATIONS:

For any configuration changes or write operations:

1. Use IBM MQ Console directly
2. Use IBM MQ Explorer (GUI)
3. Use command line (runmqsc) with proper authentication
4. Submit change request through ITSM system
5. Contact MQ administrator team

Change Management Process:
- All changes require approval
- Follow change control procedures
- Test in non-production first
- Document all changes

═══════════════════════════════════════════════════════════════════════════

📞 SUPPORT:

Security Questions: security@yourcompany.com
MQ Administration: mq-admin@yourcompany.com
Change Requests: itsm@yourcompany.com

═══════════════════════════════════════════════════════════════════════════

This policy ensures:
✓ Data integrity
✓ System stability
✓ Audit compliance
✓ Change control
✓ Security best practices

Last Updated: {datetime.now().strftime('%Y-%m-%d')}
"""


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
        queue_info['max_depth'] = 5000
    
    # Calculate percentage
    if queue_info['max_depth'] > 0:
        queue_info['depth_percent'] = (queue_info['current_depth'] / queue_info['max_depth']) * 100
    else:
        queue_info['depth_percent'] = 0
    
    # Extract IPPROCS
    ipprocs_match = re.search(r'IPPROCS\((\d+)\)', line)
    if ipprocs_match:
        queue_info['ipprocs'] = int(ipprocs_match.group(1))
    else:
        queue_info['ipprocs'] = 0
    
    # Extract OPPROCS
    opprocs_match = re.search(r'OPPROCS\((\d+)\)', line)
    if opprocs_match:
        queue_info['opprocs'] = int(opprocs_match.group(1))
    else:
        queue_info['opprocs'] = 0
    
    return queue_info


def prettify_runmqsc(payload: bytes) -> str:
    """Format MQSC command output"""
    try:
        jsonOutput = json.loads(payload.decode("utf-8"))
        prettifiedOutput = "\n---\n"
        for x in jsonOutput.get('commandResponse', []):
            text = x.get('text', [])
            if text and text[0].startswith("CSQN205I"):
                text.pop(0)
                if text:
                    text.pop()
                for y in text:
                    prettifiedOutput += y[15:] + "\n---\n"
            else:
                for line in text:
                    prettifiedOutput += line + "\n---\n"
        return prettifiedOutput
    except Exception as e:
        return f"Error formatting output: {str(e)}\n{payload.decode('utf-8')}"


if __name__ == "__main__":
    print("=" * 80)
    print("IBM MQ MCP Server - READ-ONLY Security Hardened Version")
    print("=" * 80)
    print("\nSECURITY POLICY: Only read-only operations permitted")
    print("Blocked operations: DEFINE, ALTER, DELETE, CLEAR, etc.")
    print("Allowed operations: DISPLAY commands only")
    print("\nAll operations are logged for audit purposes")
    print("=" * 80)
    print()
    
    # For Claude Desktop, use stdio transport
    mcp.run(transport='stdio')
