# Multi Queue Manager Configuration

The MQ MCP server has been updated to support querying multiple queue managers running on different ports.

## Current Configuration

The server is now configured to connect to both:

1. **QM1** on `https://localhost:9443/ibmmq/rest/v3/admin/`
2. **QM2** on `https://localhost:9444/ibmmq/rest/v3/admin/`

## Configuration Structure

In [mqmcpserver.py](mqmcpserver.py), the queue managers are defined in the `MQ_SERVERS` dictionary:

```python
MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd"
    },
    "QM2": {
        "url": "https://localhost:9444/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd"
    }
}
```

## How It Works

### dspmq Tool

The `dspmq()` tool now:
- Queries **all** configured MQ servers
- Combines the results from all servers
- Returns a unified list of all queue managers and their status

**Example query in Claude Desktop:**
```
Show me all queue managers
```

**Expected output:**
```
---
name = QM1, running = running
---
name = QM2, running = running
---
```

### runmqsc Tool

The `runmqsc()` tool now:
- Automatically determines which server to use based on the queue manager name
- If the queue manager name matches a key in `MQ_SERVERS`, uses that specific server
- Otherwise, uses the first configured server as a fallback

**Example queries in Claude Desktop:**
```
Run "DISPLAY QLOCAL(*)" on QM1
```

```
List all queues on QM2
```

```
What's the depth of SYSTEM.DEFAULT.LOCAL.QUEUE on QM1?
```

## Adding More Queue Managers

To add additional queue managers, simply add them to the `MQ_SERVERS` dictionary:

```python
MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd"
    },
    "QM2": {
        "url": "https://localhost:9444/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd"
    },
    "QM3": {
        "url": "https://remote-server:9443/ibmmq/rest/v3/admin/",
        "username": "mqadmin",
        "password": "securepassword"
    }
}
```

## Using with Claude Desktop

After updating the configuration:

1. **No need to change the Claude Desktop config** - it remains the same
2. **Restart Claude Desktop** if it's currently running
3. **Test the multi-QM support:**

Ask questions like:
- "Show me all queue managers" → will list both QM1 and QM2
- "Is QM1 running?" → will check QM1 status
- "Is QM2 running?" → will check QM2 status
- "List queues on QM1" → will query QM1 specifically
- "List queues on QM2" → will query QM2 specifically

## Verification

Both queue managers are currently running and accessible:

```bash
# Test QM1
curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/ \
  -u admin:passw0rd \
  -H "ibm-mq-rest-csrf-token: token"

# Test QM2
curl -k https://localhost:9444/ibmmq/rest/v3/admin/qmgr/ \
  -u admin:passw0rd \
  -H "ibm-mq-rest-csrf-token: token"
```

## Security Notes

⚠️ **Important:**
- Each queue manager can have different credentials
- Update usernames and passwords as needed for your environment
- Use environment variables for production deployments instead of hardcoding passwords
- Consider using TLS certificates for production use

## Troubleshooting

### Queue manager not found
If a specific queue manager isn't responding:
1. Verify the container is running: `docker ps | grep mq`
2. Check the port mapping is correct
3. Verify the REST API is accessible: `curl -k https://localhost:<port>/ibmmq/rest/v3/admin/qmgr/`

### Wrong queue manager responding
If commands are going to the wrong queue manager:
- Ensure the queue manager name in your question exactly matches the key in `MQ_SERVERS`
- The lookup is case-sensitive (QM1 ≠ qm1)

### Credentials not working
- Verify credentials with curl (see verification section above)
- Check that the user has appropriate permissions in the mqweb server
- Ensure the user is a member of MQWebAdmin or MQWebUser role
