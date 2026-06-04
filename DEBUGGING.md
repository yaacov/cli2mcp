# Debugging the MCP Server

## Start the curl MCP server

Terminal 1 -- start the server on HTTP:

```bash
uv run cli2mcp serve examples/curl.tools.json -t streamable-http
```

Leave it running. All commands below run in a **second terminal**.

## Initialize a session

Every MCP conversation starts with a handshake.

`examples/requests/1_initialize.json`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "debug",
      "version": "1.0"
    }
  }
}
```

Send it and capture the session ID:

```bash
SESSION=$(curl -s -D- -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d @examples/requests/1_initialize.json \
  | grep -i mcp-session-id | awk '{print $2}' | tr -d '\r')

echo "Session: $SESSION"
```

Confirm the handshake.

`examples/requests/2_initialized.json`:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H "Mcp-Session-Id: $SESSION" \
  -d @examples/requests/2_initialized.json
```

## List available tools

`examples/requests/3_list_tools.json`:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}
```

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -d @examples/requests/3_list_tools.json \
  | grep '^data:' | sed 's/^data: //' | python3 -m json.tool
```

Expected: a `tools` array with `curl` and its `inputSchema` listing
all available arguments (`data`, `output`, `url`, etc.).

## Call the tool to fetch a web page

`examples/requests/4_call_tool.json`:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "curl",
    "arguments": {
      "url": "http://example.com"
    }
  }
}
```

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -d @examples/requests/4_call_tool.json \
  | grep '^data:' | sed 's/^data: //' | python3 -m json.tool
```

Expected: `content[0].text` contains the HTML of http://example.com.

## What just happened

```
You (curl)  --->  MCP server (localhost:8000)  --->  curl  --->  example.com
   HTTP POST         reads tools.json                 subprocess     HTML
   JSON-RPC          builds command                   runs it        returned
```

1. Your curl sent a JSON-RPC `tools/call` to the MCP server
2. The server looked up `curl` in `examples/curl.tools.json`
3. It built the command: `curl http://example.com`
4. It ran it with `subprocess.run()`
5. It returned stdout as MCP tool output
