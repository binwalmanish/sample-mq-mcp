# MCP Server Security Guide
## Restricting AI Agents to Read-Only Operations

---

## Executive Summary

This document explains how to restrict AI agents (like Claude) to **read-only operations** when managing IBM MQ infrastructure, preventing any destructive or configuration-changing actions.

**Key Security Principles:**
- ✅ **Allow:** Monitoring, health checks, capacity planning (DISPLAY commands)
- ❌ **Block:** Creating, modifying, deleting queues or configurations (DEFINE, ALTER, DELETE)
- 🔒 **Enforce:** Multi-layer validation with audit logging

---

## Table of Contents

1. [Security Architecture](#security-architecture)
2. [What We Block](#what-we-block)
3. [What We Allow](#what-we-allow)
4. [How Protection Works](#how-protection-works)
5. [Implementation Details](#implementation-details)
6. [Testing Security](#testing-security)
7. [Audit & Compliance](#audit--compliance)
8. [Best Practices](#best-practices)

---

## Security Architecture

### Three-Layer Security Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: Command Validation               │
│  • Validate MQSC command syntax                             │
│  • Check against blocked command list                       │
│  • Reject non-DISPLAY commands                              │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 2: Keyword Filtering                │
│  • Scan for dangerous keywords (DELETE, CLEAR, etc.)        │
│  • Detect obfuscation attempts                              │
│  • Validate command parameters                              │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: HTTP Method Control              │
│  • Allow only GET requests                                   │
│  • Block POST, PUT, DELETE, PATCH                           │
│  • Validate REST API endpoints                              │
└─────────────────────────────────────────────────────────────┘
                             ↓
                    ✓ Execute Read-Only Command
```

---

## What We Block

### ❌ Blocked MQSC Commands

| Command | Purpose | Why Blocked |
|---------|---------|-------------|
| **DEFINE** | Create queues, channels, etc. | Creates new objects |
| **ALTER** | Modify configurations | Changes existing configs |
| **DELETE** | Remove queues, channels, etc. | Destroys objects |
| **CLEAR** | Clear queue contents | Deletes messages |
| **START** | Start channels, listeners | Changes runtime state |
| **STOP** | Stop channels, listeners | Changes runtime state |
| **RESET** | Reset statistics | Modifies counters |
| **REFRESH** | Refresh configurations | Applies config changes |
| **SUSPEND** | Suspend queue manager | Changes QM state |
| **RESUME** | Resume queue manager | Changes QM state |
| **SET** | Modify settings | Changes configuration |
| **ARCHIVE** | Archive logs | System operation |
| **RECOVER** | Recover data | System operation |
| **MOVE** | Move messages | Modifies queue contents |

### ❌ Blocked REST API Operations

```
❌ POST   /ibmmq/rest/v2/messaging/qmgr/*/queue/*/message     (Put messages)
❌ DELETE /ibmmq/rest/v2/messaging/qmgr/*/queue/*/message     (Get messages - destructive)
❌ POST   /ibmmq/rest/v3/admin/action/qmgr/*/mqsc             (Execute MQSC - validated separately)
❌ PUT    /ibmmq/rest/v3/admin/qmgr/*/queue/*                 (Update queue)
❌ DELETE /ibmmq/rest/v3/admin/qmgr/*/queue/*                 (Delete queue)
❌ POST   /ibmmq/rest/v3/admin/qmgr/*/queue/*                 (Create queue)
```

### ❌ Blocked Message Operations

- Cannot put messages to any queue
- Cannot get messages from any queue (even browse mode)
- Cannot clear queue contents
- Cannot modify message properties
- Cannot move messages between queues

---

## What We Allow

### ✅ Allowed MQSC Commands

Only `DISPLAY` commands are permitted:

```mqsc
✅ DISPLAY QLOCAL(*)          - Display local queues
✅ DISPLAY QREMOTE(*)         - Display remote queues
✅ DISPLAY QALIAS(*)          - Display alias queues
✅ DISPLAY QMODEL(*)          - Display model queues
✅ DISPLAY CHANNEL(*)         - Display channels
✅ DISPLAY CHSTATUS(*)        - Display channel status
✅ DISPLAY CONN(*)            - Display connections
✅ DISPLAY CLUSQMGR(*)        - Display cluster queue managers
✅ DISPLAY QMSTATUS(*)        - Display queue manager status
✅ DISPLAY LISTENER(*)        - Display listeners
✅ DISPLAY NAMELIST(*)        - Display namelists
✅ DISPLAY PROCESS(*)         - Display processes
✅ DISPLAY SERVICE(*)         - Display services
✅ DISPLAY TOPIC(*)           - Display topics
✅ DISPLAY SUB(*)             - Display subscriptions
✅ DISPLAY PUBSUB(*)          - Display pub/sub status
```

### ✅ Allowed REST API Operations

Only `GET` requests are permitted:

```
✅ GET /ibmmq/rest/v3/admin/qmgr/                             (List queue managers)
✅ GET /ibmmq/rest/v3/admin/qmgr/{qmgrName}                   (Get QM details)
✅ GET /ibmmq/rest/v3/admin/qmgr/{qmgrName}/queue/           (List queues)
✅ GET /ibmmq/rest/v3/admin/qmgr/{qmgrName}/queue/{name}     (Get queue details)
✅ GET /ibmmq/rest/v3/admin/qmgr/{qmgrName}/channel/         (List channels)
```

### ✅ Allowed Operations

1. **Health Monitoring**
   - Check queue depths
   - Monitor channel status
   - Track application connections
   - View dead letter queues

2. **Capacity Planning**
   - Analyze queue growth trends
   - Generate capacity reports
   - Forecast resource needs

3. **Performance Analysis**
   - Collect performance metrics
   - Track message rates
   - Monitor resource utilization

4. **Troubleshooting**
   - Investigate connectivity issues
   - Identify bottlenecks
   - Analyze cluster health

---

## How Protection Works

### 1. Command Validation Function

```python
def validate_mqsc_command(mqsc_command: str) -> tuple[bool, str]:
    """
    Validate that an MQSC command is read-only and safe to execute.
    
    Security Checks:
    1. Extract command verb (first word)
    2. Check if in BLOCKED_MQSC_COMMANDS list
    3. Check if in ALLOWED_MQSC_COMMANDS list
    4. Scan for dangerous keywords
    5. Return validation result
    """
    
    command_upper = mqsc_command.strip().upper()
    command_verb = command_upper.split()[0]
    
    # Check blocked list
    if command_verb in BLOCKED_MQSC_COMMANDS:
        return False, f"BLOCKED: '{command_verb}' commands not allowed"
    
    # Check allowed list
    if command_verb not in ALLOWED_MQSC_COMMANDS:
        return False, f"BLOCKED: Only DISPLAY commands permitted"
    
    # Scan for dangerous patterns
    dangerous_patterns = [r'\bCLEAR\b', r'\bDELETE\b', r'\bALTER\b']
    for pattern in dangerous_patterns:
        if re.search(pattern, command_upper):
            return False, f"BLOCKED: Dangerous keyword detected"
    
    return True, ""
```

### 2. Security Wrapper

```python
async def execute_mqsc_readonly(qmgr_name: str, mqsc_command: str) -> str:
    """
    Execute MQSC command with security validation.
    
    Flow:
    1. Validate command is read-only
    2. If blocked → Log security event, return error
    3. If allowed → Log event, execute command
    4. Return results
    """
    
    # Validate
    is_valid, error_msg = validate_mqsc_command(mqsc_command)
    
    if not is_valid:
        # Log security violation
        log_security_event("BLOCKED_MQSC_COMMAND", f"Blocked: {mqsc_command}", "CRITICAL")
        return "SECURITY POLICY VIOLATION: " + error_msg
    
    # Log allowed operation
    log_security_event("ALLOWED_MQSC_COMMAND", f"Executing: {mqsc_command}", "INFO")
    
    # Execute command
    # ... REST API call ...
```

### 3. Security Event Logging

```python
def log_security_event(event_type: str, details: str, severity: str):
    """
    Log security events for audit trail.
    
    Logged Information:
    - Timestamp (ISO format)
    - Event type (BLOCKED_COMMAND, ALLOWED_COMMAND, etc.)
    - Details (command, queue manager, etc.)
    - Severity (INFO, WARNING, CRITICAL)
    - User context (if available)
    """
    
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] SECURITY [{severity}] {event_type}: {details}"
    
    # Log to stderr
    print(log_message, file=sys.stderr)
    
    # In production, also send to:
    # - SIEM system (Splunk, ELK, etc.)
    # - Security monitoring platform
    # - Audit database
```

---

## Implementation Details

### Configuration Files

#### 1. Security Configuration

```python
# List of BLOCKED MQSC commands
BLOCKED_MQSC_COMMANDS = [
    'DEFINE', 'ALTER', 'DELETE', 'CLEAR', 'START', 'STOP', 
    'RESET', 'REFRESH', 'SUSPEND', 'RESUME', 'PING', 'RESOLVE', 
    'MOVE', 'SET', 'ARCHIVE', 'RECOVER'
]

# List of ALLOWED MQSC commands
ALLOWED_MQSC_COMMANDS = [
    'DISPLAY'  # Only DISPLAY commands allowed
]

# HTTP methods allowed
ALLOWED_HTTP_METHODS = ['GET']
```

#### 2. MCP Server Configuration

```python
# Use read-only user credentials where possible
MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "mqreadonly",  # ← Use read-only user
        "password": "secure_password",
        "region": "us-east",
    }
}
```

### IBM MQ User Configuration

Create a **read-only user** in IBM MQ:

```mqsc
DEFINE AUTHINFO(MQREADONLY.AUTHINFO) +
       AUTHTYPE(IDPWOS) +
       CHCKCLNT(REQUIRED)

ALTER QMGR CONNAUTH(MQREADONLY.AUTHINFO)

REFRESH SECURITY TYPE(CONNAUTH)

# Grant read-only permissions
SET AUTHREC PRINCIPAL('mqreadonly') +
            OBJTYPE(QMGR) +
            AUTHADD(CONNECT, INQ, DSP)

SET AUTHREC PROFILE('*') +
            PRINCIPAL('mqreadonly') +
            OBJTYPE(QUEUE) +
            AUTHADD(INQ, DSP, BROWSE)

SET AUTHREC PROFILE('*') +
            PRINCIPAL('mqreadonly') +
            OBJTYPE(CHANNEL) +
            AUTHADD(INQ, DSP)

# Explicitly deny write operations
SET AUTHREC PRINCIPAL('mqreadonly') +
            OBJTYPE(QUEUE) +
            AUTHRM(PUT, GET, PASSALL, PASSID, SETALL, SETID, ALLMQI, CRT, DLT, CHG)
```

---

## Testing Security

### Test Suite

#### Test 1: Block CREATE Operations

```python
# User asks: "Create a new queue called TEST.QUEUE"

Expected Result:
╔════════════════════════════════════════════════════════════════╗
║              SECURITY POLICY VIOLATION                          ║
╚════════════════════════════════════════════════════════════════╝

❌ COMMAND BLOCKED: 'DEFINE' commands are not allowed.

Requested Command: DEFINE QLOCAL(TEST.QUEUE)
This security event has been logged for audit purposes.
```

#### Test 2: Block DELETE Operations

```python
# User asks: "Delete all messages from DEV.QUEUE.1"

Expected Result:
╔════════════════════════════════════════════════════════════════╗
║              SECURITY POLICY VIOLATION                          ║
╚════════════════════════════════════════════════════════════════╝

❌ COMMAND BLOCKED: 'CLEAR' commands are not allowed.

Requested Command: CLEAR QLOCAL(DEV.QUEUE.1)
This security event has been logged for audit purposes.
```

#### Test 3: Block MODIFY Operations

```python
# User asks: "Change the max depth of DEV.QUEUE.1 to 10000"

Expected Result:
╔════════════════════════════════════════════════════════════════╗
║              SECURITY POLICY VIOLATION                          ║
╚════════════════════════════════════════════════════════════════╝

❌ COMMAND BLOCKED: 'ALTER' commands are not allowed.

Requested Command: ALTER QLOCAL(DEV.QUEUE.1) MAXDEPTH(10000)
This security event has been logged for audit purposes.
```

#### Test 4: Allow READ Operations

```python
# User asks: "Show me the queue depth of DEV.QUEUE.1"

Expected Result:
═══════════════════════════════════════════════════════════════
HEALTH CHECK REPORT (READ-ONLY): QM1
═══════════════════════════════════════════════════════════════

Queue: DEV.QUEUE.1
Current Depth: 5 messages
Max Depth: 5000
Utilization: 0.1%

✅ Operation completed successfully
```

#### Test 5: Detect Obfuscation Attempts

```python
# User asks: "Display queues and also delete them"

Expected Result:
╔════════════════════════════════════════════════════════════════╗
║              SECURITY POLICY VIOLATION                          ║
╚════════════════════════════════════════════════════════════════╝

❌ COMMAND BLOCKED: Command contains dangerous keyword.

Detected Keywords: DELETE
This security event has been logged for audit purposes.
```

### Automated Test Script

```python
import asyncio

async def test_security():
    """Test security restrictions"""
    
    tests = [
        # Blocked operations
        ("DEFINE QLOCAL(TEST)", False, "DEFINE blocked"),
        ("ALTER QLOCAL(DEV.QUEUE.1) MAXDEPTH(1000)", False, "ALTER blocked"),
        ("DELETE QLOCAL(TEST)", False, "DELETE blocked"),
        ("CLEAR QLOCAL(DEV.QUEUE.1)", False, "CLEAR blocked"),
        ("START CHANNEL(MY.CHANNEL)", False, "START blocked"),
        ("STOP CHANNEL(MY.CHANNEL)", False, "STOP blocked"),
        
        # Allowed operations
        ("DISPLAY QLOCAL(*)", True, "DISPLAY allowed"),
        ("DISPLAY CHSTATUS(*)", True, "DISPLAY CHSTATUS allowed"),
        ("DISPLAY CONN(*)", True, "DISPLAY CONN allowed"),
    ]
    
    for command, should_pass, description in tests:
        is_valid, error_msg = validate_mqsc_command(command)
        
        if should_pass and is_valid:
            print(f"✅ PASS: {description}")
        elif not should_pass and not is_valid:
            print(f"✅ PASS: {description}")
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Expected: {'ALLOW' if should_pass else 'BLOCK'}")
            print(f"   Got: {'ALLOW' if is_valid else 'BLOCK'}")

if __name__ == "__main__":
    asyncio.run(test_security())
```

---

## Audit & Compliance

### Security Logging

All operations are logged with:

```
[2025-01-15T10:30:45.123Z] SECURITY [INFO] ALLOWED_MQSC_COMMAND: 
  QM: QM1
  Command: DISPLAY QLOCAL(*)
  User: claude_mcp
  Result: Success

[2025-01-15T10:31:12.456Z] SECURITY [CRITICAL] BLOCKED_MQSC_COMMAND:
  QM: QM1
  Command: DELETE QLOCAL(TEST.QUEUE)
  User: claude_mcp
  Result: Blocked - Security Policy Violation
```

### Integration with SIEM

```python
def send_to_siem(event_type: str, details: str, severity: str):
    """Send security events to SIEM system"""
    
    # Example: Splunk
    import requests
    splunk_url = "https://splunk.company.com:8088/services/collector"
    splunk_token = "YOUR-HEC-TOKEN"
    
    event = {
        "time": datetime.now().timestamp(),
        "host": socket.gethostname(),
        "source": "mq_mcp_server",
        "sourcetype": "mcp_security",
        "event": {
            "type": event_type,
            "details": details,
            "severity": severity,
            "service": "ibm_mq_mcp"
        }
    }
    
    requests.post(
        splunk_url,
        headers={"Authorization": f"Splunk {splunk_token}"},
        json=event
    )
```

### Compliance Reports

Generate monthly security reports:

```python
async def generate_security_report(month: str) -> str:
    """
    Generate monthly security compliance report
    
    Includes:
    - Total operations performed
    - Blocked operations count
    - Top blocked commands
    - Security violations by user
    - Compliance status
    """
    
    # Query audit logs
    # Generate report
    # Return formatted output
```

---

## Best Practices

### 1. Principle of Least Privilege

```python
# ✅ GOOD: Use read-only user
MQ_SERVERS = {
    "QM1": {
        "username": "mqreadonly",  # Limited permissions
    }
}

# ❌ BAD: Use admin user
MQ_SERVERS = {
    "QM1": {
        "username": "admin",  # Full permissions (risky!)
    }
}
```

### 2. Defense in Depth

- **Layer 1:** Application-level validation (MCP server)
- **Layer 2:** IBM MQ user permissions (read-only user)
- **Layer 3:** Network-level controls (firewall rules)
- **Layer 4:** Audit logging (SIEM integration)

### 3. Regular Security Audits

```bash
# Monthly security audit checklist
☐ Review blocked operation logs
☐ Verify read-only user permissions
☐ Test security controls
☐ Update blocked command list
☐ Review SIEM alerts
☐ Update documentation
```

### 4. Incident Response

If a security violation occurs:

1. **Immediate:**
   - Log the event (automatic)
   - Block the operation (automatic)
   - Alert security team

2. **Investigation:**
   - Review audit logs
   - Determine intent (malicious vs mistake)
   - Interview user if needed

3. **Remediation:**
   - Update security rules if needed
   - Additional training if required
   - Enhance monitoring

### 5. User Education

Train AI users on:
- What operations are allowed
- Why restrictions exist
- How to request write operations
- Proper escalation procedures

---

## Advanced Security Features

### 1. Rate Limiting

```python
from collections import defaultdict
from datetime import datetime, timedelta

# Track operations per user
operation_tracker = defaultdict(list)

def check_rate_limit(user: str, max_ops: int = 100, window_minutes: int = 60):
    """Prevent abuse through rate limiting"""
    
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    
    # Remove old operations
    operation_tracker[user] = [
        op_time for op_time in operation_tracker[user]
        if op_time > cutoff
    ]
    
    # Check if over limit
    if len(operation_tracker[user]) >= max_ops:
        return False, f"Rate limit exceeded: {max_ops} ops per {window_minutes} min"
    
    # Record this operation
    operation_tracker[user].append(now)
    return True, ""
```

### 2. IP Whitelisting

```python
ALLOWED_IPS = [
    "10.0.0.0/8",      # Internal network
    "192.168.1.0/24",  # Office network
]

def check_ip_whitelist(client_ip: str) -> bool:
    """Only allow operations from approved networks"""
    import ipaddress
    
    client = ipaddress.ip_address(client_ip)
    
    for allowed_range in ALLOWED_IPS:
        if client in ipaddress.ip_network(allowed_range):
            return True
    
    return False
```

### 3. Time-Based Restrictions

```python
def check_time_restrictions() -> tuple[bool, str]:
    """Only allow operations during business hours"""
    
    now = datetime.now()
    
    # Business hours: Monday-Friday, 6 AM - 10 PM
    if now.weekday() >= 5:  # Weekend
        return False, "Operations restricted to weekdays"
    
    if now.hour < 6 or now.hour >= 22:
        return False, "Operations restricted to 6 AM - 10 PM"
    
    return True, ""
```

---

## Summary

### Security Guarantees

✅ **AI agents CANNOT:**
- Create queues, channels, or any objects
- Modify configurations
- Delete objects
- Clear queue contents
- Start/stop channels
- Put or get messages
- Make any configuration changes

✅ **AI agents CAN:**
- View queue depths and status
- Monitor channel connectivity
- Check application connections
- Analyze performance metrics
- Generate capacity reports
- Detect anomalies
- Provide recommendations

### Protection Mechanisms

1. **Command Validation:** Blocks non-DISPLAY commands
2. **Keyword Filtering:** Detects dangerous operations
3. **HTTP Method Control:** Only GET requests allowed
4. **Audit Logging:** All operations logged
5. **User Permissions:** Read-only MQ user recommended

### Compliance

- **SOC 2:** Audit logging and access controls
- **PCI-DSS:** Separation of duties, least privilege
- **HIPAA:** Access logging and monitoring
- **ISO 27001:** Security controls and documentation

---

## Quick Reference

### ✅ Safe Commands to Ask Claude

- "Show me queue depths on QM1"
- "Check health of all queue managers"
- "Monitor channel status"
- "Detect any anomalies"
- "Generate capacity report"
- "What's the connection status?"

### ❌ Commands That Will Be Blocked

- "Create a new queue called TEST"
- "Delete the TEST queue"
- "Clear all messages from DEV.QUEUE.1"
- "Stop the channel MY.CHANNEL"
- "Change max depth to 10000"
- "Put a message to DEV.QUEUE.1"

---

**Last Updated:** 2025-01-15  
**Version:** 2.0  
**Security Review:** Quarterly
