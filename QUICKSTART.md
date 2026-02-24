# Quick Start Guide: MQ MCP Server for Claude Desktop

This guide will help you set up and use the MQ MCP Server with Claude Desktop to query your containerized IBM MQ queue manager.

## Prerequisites

- IBM MQ container running ()
- Python 3.10 or higher
- Claude Desktop installed
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
   - `runmqsc` - Run MQSC commands for getting queue details.

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

Enjoy querying your MQ queue manager with natural language! 

# Sample IBM MQ MCP server

MCP (Model Context Protocol) is an open standard that allows LLMs and AI agents to discover and interact with external services such as databases, REST APIs, files, and other resources.
You can read up on the details of MCP [here](https://modelcontextprotocol.io/introduction).

This repo contains a simple MCP server, written in Python, that exposes a subset of the [MQ Administrative REST API](https://www.ibm.com/docs/en/ibm-mq/9.4.x?topic=administering-administration-using-rest-api) as two MCP tools:

- dsqmq: lists any queue managers that are local to the mqweb server, and whether they are running or not
- runmqsc: runs any MQSC command against a specific queue manager. This makes use of the [plain text MQSC API](https://www.ibm.com/docs/en/ibm-mq/9.4.x?topic=adminactionqmgrqmgrnamemqsc-post-plain-text-mqsc-command) 

You can use this MCP server with any LLM which has an MCP client in it, for example [IBM Bob](https://www.ibm.com/products/bob), to allow that LLM to interact with, and potentially configure, your queue managers.
1. I have used Anthropic Claude Sonet model for LLM
2. Used Claude Desktop for AIAgent for chat
3. claude_desktop_config.json file has command to run the MCP server when Claude Desktop/Agent/MCP clinet starts.


## Getting the MQ MCP server running

This example was created based on these [instructions](https://modelcontextprotocol.io/quickstart/server). To get the MQ MCP server running, follow these steps:

- The MQ MCP server uses the MQ Administrative REST API. Ensure that you have the mqweb server running as part of a full MQ for distributed installation with one or more queue managers. This doesn't have to be on your local machine
- Ensure that you have installed Python 3.10 or higher
- Install uv and set up your Python project
    - (MacOS/Linux): **curl -LsSf https://astral.sh/uv/install.sh | sh**
    - (Windows): **powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"**
- Restart your terminal
- Clone this repo into a working directory, e.g. **C:\work**
- Change into the mq-mcp-server directory: **cd mq-mcp-server**
- Install dependencies: **uv add "mcp[cli]" httpx**
- Open **mqmcpserver.py** in your editor of choice and change:
    - URL_BASE to point to the base URL of your mqweb server
    - USER_NAME and PASSWORD to the username and password of the user you want to run MQSC commands as. Bear in mind that if the user is a member of the MQWebAdmin or MQWebUser roles then requests to the MQ MCP server will be able to change your MQ configuration, so you might only want to use these roles in a test environment
- Save your changes
- Start the MQ MCP server by running: **uv run mqmcpserver.py**

By default the MQ MCP server will be listening on http://127.0.0.1:8000/mcp using the streamable HTTP protocol. You can adjust the host name and port number, or use a different protocol using the information provided [here](https://github.com/jlowin/fastmcp#running-your-server).
Some alternatives are included, with comments, in the code.

## Connecting the MCP server to an LLM

Follow the instructions provided by your LLM for connecting to your new MCP server. For example you could connect to it using [IBM Bob](https://www.ibm.com/products/bob) or [IBM Watsonx Orchestrate](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=servers-importing-tools-from-mcp-server). 
Alternatively, a [wide range](https://modelcontextprotocol.io/clients) of other LLMs support MCP.
