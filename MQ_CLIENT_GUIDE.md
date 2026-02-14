# MQ Client Programs - Put and Get Messages

This guide explains how to use the MQ client programs to send and receive messages from your containerized MQ queue manager using the REST API.

## Programs

1. **mq_put_message.py** - Writes messages to a queue
2. **mq_get_message.py** - Reads messages from a queue

✨ **No MQ client libraries required!** These programs use the MQ REST Messaging API.

## Prerequisites

- QM1 container running on localhost:9443
- Python 3.10 or higher
- httpx library (already installed)

## Configuration

Both programs are configured to connect to:

- **Queue Manager**: QM1
- **REST API**: https://localhost:9443/ibmmq/rest/v2/messaging
- **Queue**: DEV.QUEUE.1
- **User**: app
- **Password**: passw0rd

## Quick Start

### 1. Create the Test Queue

First, create the queue using Claude Desktop with the MCP server:

```
Create a local queue named DEV.QUEUE.1 on QM1
```

Or use docker directly:
```bash
docker exec -it <container-id> runmqsc QM1
DEFINE QLOCAL(DEV.QUEUE.1) DEFPSIST(YES)
end
```

### 2. Put a Message

**Default message (with timestamp):**
```bash
uv run python mq_put_message.py
```

**Custom message:**
```bash
uv run python mq_put_message.py "Hello from MQ!"
```

**Multi-word message:**
```bash
uv run python mq_put_message.py "This is a test message with multiple words"
```

### 3. Get a Message

**Get one message (removes from queue):**
```bash
uv run python mq_get_message.py
```

**Get all messages:**
```bash
uv run python mq_get_message.py --all
```

## Example Workflow

### Send and Receive Messages

```bash
# Put some messages
uv run python mq_put_message.py "First message"
uv run python mq_put_message.py "Second message"
uv run python mq_put_message.py "Third message"

# Check queue depth using Claude Desktop
# Ask: "What's the depth of DEV.QUEUE.1?"

# Get one message
uv run python mq_get_message.py

# Get remaining messages
uv run python mq_get_message.py --all
```

## Output Examples

### Put Message Output
```
============================================================
MQ Message Writer - Put Message to Queue (REST API)
============================================================
Queue Manager: QM1
Queue: DEV.QUEUE.1
REST API: https://localhost:9443/ibmmq/rest/v2/messaging
============================================================

Sending message: Hello from MQ!

✓ Message sent successfully!

Response status: 201
Message ID: 414d5120514d312020202020202020201f678167090a0040

============================================================
SUCCESS - Message sent to queue!
============================================================
```

### Get Message Output
```
============================================================
MQ Message Reader - Get Message from Queue (REST API)
============================================================
Queue Manager: QM1
Queue: DEV.QUEUE.1
REST API: https://localhost:9443/ibmmq/rest/v2/messaging
============================================================

Current queue depth: 1

Retrieving message...

============================================================
MESSAGE RECEIVED
============================================================
Message: Hello from MQ!
Message ID: 414d5120514d312020202020202020201f678167090a0040
Correlation ID: 000000000000000000000000000000000000000000000000
Format: MQSTR
Priority: 0
============================================================

============================================================
SUCCESS - Message retrieved
============================================================
```

## Advanced Usage

### Modify Queue Name

Edit the programs and change the `QUEUE_NAME` variable:

```python
QUEUE_NAME = 'YOUR.QUEUE.NAME'
```

### Connect to QM2

Change these variables in both programs:

```python
QM_NAME = 'QM2'
MQ_REST_BASE = 'https://localhost:9444/ibmmq/rest/v2/messaging'
```

### Use Admin Credentials

For admin access, change:

```python
USER = 'admin'
PASSWORD = 'passw0rd'
```

## Troubleshooting

### HTTP 401 Unauthorized

The user doesn't have permission to access the queue.

**Solution:** Grant permissions via MQSC:
```bash
docker exec -it <container-id> runmqsc QM1
SET AUTHREC OBJTYPE(QMGR) PRINCIPAL('app') AUTHADD(CONNECT,INQ)
SET AUTHREC PROFILE('DEV.**') OBJTYPE(QUEUE) PRINCIPAL('app') AUTHADD(PUT,GET,BROWSE,INQ)
end
```

### HTTP 404 Not Found

The queue doesn't exist.

**Solution:** Create the queue:
```bash
docker exec -it <container-id> runmqsc QM1
DEFINE QLOCAL(DEV.QUEUE.1) DEFPSIST(YES)
end
```

Or ask Claude Desktop:
```
Create a queue named DEV.QUEUE.1 on QM1
```

### Connection refused

Can't connect to the MQ web server.

**Solution:**
- Check container is running: `docker ps | grep mq`
- Check port mapping: `docker port <container-id>`
- Verify REST API is accessible:
  ```bash
  curl -k https://localhost:9443/ibmmq/rest/v2/messaging/qmgr/QM1 \
    -u app:passw0rd -H "ibm-mq-rest-csrf-token: value"
  ```

### SSL/TLS errors

**Solution:** The programs use `verify=False` to skip SSL verification for development. This is already handled.

## Integration with Claude Desktop

You can combine the MCP server with these client programs:

**Workflow Example:**

1. **Create queue via Claude Desktop:**
   ```
   Create a local queue named DEV.QUEUE.1 on QM1
   ```

2. **Put messages with Python:**
   ```bash
   uv run python mq_put_message.py "Message 1"
   uv run python mq_put_message.py "Message 2"
   ```

3. **Check queue depth via Claude Desktop:**
   ```
   What's the depth of DEV.QUEUE.1?
   ```

4. **Get messages with Python:**
   ```bash
   uv run python mq_get_message.py --all
   ```

5. **Verify empty via Claude Desktop:**
   ```
   Is DEV.QUEUE.1 empty?
   ```

## Testing the Full Workflow

```bash
# 1. Create queue via Claude Desktop
# Ask: "Create a queue named DEV.QUEUE.1 on QM1"

# 2. Put messages
for i in {1..5}; do
  uv run python mq_put_message.py "Message $i"
done

# 3. Check queue depth via Claude Desktop
# Ask: "What's the depth of DEV.QUEUE.1?"

# 4. Get all messages
uv run python mq_get_message.py --all

# 5. Verify queue is empty via Claude Desktop
# Ask: "What's the depth of DEV.QUEUE.1?"
```

## Comparison: REST API vs MQ Client

| Feature | REST API (These Programs) | MQ Client (pymqi) |
|---------|---------------------------|-------------------|
| Installation | ✅ No extra libraries | ❌ Requires MQ client installation |
| Platform | ✅ Any platform | ⚠️ Platform-specific binaries |
| Setup | ✅ Works immediately | ❌ Complex setup |
| Performance | ⚠️ HTTP overhead | ✅ Native protocol |
| Features | ⚠️ Basic operations | ✅ Full MQ functionality |
| Use Case | ✅ Development, testing | ✅ Production applications |

## REST API Limitations

- No browse mode (messages are always removed when retrieved)
- Slower than native MQ client
- Limited transaction support
- Basic message properties only

For production applications with high volume or complex requirements, consider using the native MQ client libraries (pymqi or IBM MQ JMS).

## References

- [IBM MQ REST Messaging API](https://www.ibm.com/docs/en/ibm-mq/9.4?topic=api-rest-messaging)
- [IBM MQ REST API Examples](https://www.ibm.com/docs/en/ibm-mq/9.4?topic=messaging-examples-rest-api)
- [IBM MQ Container Documentation](https://github.com/ibm-messaging/mq-container)
