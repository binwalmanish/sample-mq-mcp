# Quick Start Guide: MQ MCP Server for Claude Desktop

This guide will help you set up and use the MQ MCP Server with Claude Desktop to query your containerized IBM MQ queue manager.

## Prerequisites

- IBM MQ container running (you already have this!)
- Python 3.10 or higher
- Claude Desktop app installed
- `uv` package manager

## Step 1: Verify Your MQ Container is Running

Check that your MQ container is running:
```bash
docker ps | grep mq
```

You should see your container with ports 9443 and 1414 exposed.

## Step 2: Install Dependencies

If you haven't already, install `uv` and project dependencies:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your terminal, then install dependencies
cd /Users/suchi/projects/IBM-MQ/mq-mcp-server
uv add "mcp[cli]" httpx
```

## Step 3: Test the MCP Server

Test that the server module loads correctly:

```bash
uv run python -c "import mqmcpserver; print('MCP server ready!')"
```

You should see:
```
MCP server ready!
```

Note: The MCP server uses `stdio` transport for Claude Desktop, so it won't run as a standalone HTTP server. Claude Desktop will automatically start and manage the server process.

## Step 4: Configure Claude Desktop

1. Open your Claude Desktop configuration file:
   - On macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - On Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the MQ server configuration. If the file already has content, merge this into the existing `mcpServers` section:

```json
{
  "mcpServers": {
    "mq-server": {
      "command": "/Users/suchi/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/suchi/projects/IBM-MQ/mq-mcp-server",
        "run",
        "mqmcpserver.py"
      ]
    }
  }
}
```

**Note:** If `uv` is installed in a different location on your system, find it with `which uv` and use that full path.

3. Save the file and **completely quit and restart Claude Desktop** (not just close the window - use Cmd+Q on Mac or fully exit on Windows)

## Step 5: Verify Connection in Claude Desktop

After restarting Claude Desktop:

1. Look for the 🔌 icon (plug icon) in the bottom-right corner of the input box
2. Click it to see available MCP servers
3. You should see "mq-server" listed with two tools:
   - `dspmq` - List queue managers and their status
   - `runmqsc` - Run MQSC commands

## Step 6: Try Your First Query!

In Claude Desktop, ask questions like:

- **"Is the queue manager running?"**
- **"Show me all queue managers"**
- **"List all queues on QM1"** (if your QM is named QM1)
- **"What's the depth of SYSTEM.DEFAULT.LOCAL.QUEUE on QM1?"**

Claude will automatically use the MCP tools to query your MQ container!

## Example Queries

Here are some useful questions to ask:

```
Is the queue manager running?
```

```
Run the MQSC command "DISPLAY QLOCAL(*)" on QM1
```

```
What queues exist on the queue manager?
```

```
Check the depth of the dead letter queue
```

## Troubleshooting

### Server not showing in Claude Desktop
- Make sure you completely quit and restarted Claude Desktop
- Check the Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log` (macOS)
- Verify the path in the config matches your actual directory

### Connection errors
- Verify your MQ container is running: `docker ps | grep mq`
- Check the MQ web console is accessible: `https://localhost:9443/ibmmq/console`
- Default credentials are: `admin` / `passw0rd`

### Permission errors
- Make sure `uv` is in your PATH
- Try running `uv run mqmcpserver.py` manually to see any errors

## Container Information

Your MQ container is configured with:
- **Queue Manager**: QM1 (or check with `docker ps`)
- **Admin User**: admin
- **Password**: passw0rd
- **MQ Web Console**: https://localhost:9443/ibmmq/console
- **MQ Listener**: localhost:1414

## Next Steps

Once working, you can:
- Modify `mqmcpserver.py` to add more MCP tools
- Add additional MQSC commands
- Connect to different queue managers
- Customize the credentials in `mqmcpserver.py`

Enjoy querying your MQ queue manager with natural language! 🚀
