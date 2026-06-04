# Debugging the MCP Server

## MCP transports

MCP defines two standard transports:

| Transport | When to use | How it works |
|---|---|---|
| **stdio** | Local — IDE spawns the server as a child process | JSON-RPC over stdin/stdout pipes |
| **Streamable HTTP** | Remote — server is a standalone HTTP service | JSON-RPC via POST to a single `/mcp` endpoint |

**Streamable HTTP** is the easiest to debug with `curl` because it is plain
HTTP: you POST JSON-RPC messages and read the response.  The server replies
with either `application/json` or an SSE stream (`text/event-stream`);
the Python MCP SDK currently always uses SSE, so we extract the `data:`
line from each response.

---

## Start the servers

Terminal 1 — a tiny target server so the demo is fully self-contained:

```bash
python3 -c '
from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(s): s.send_response(200); s.end_headers(); s.wfile.write(b"Hello, world!\n")
    def log_message(s, *a): pass
HTTPServer(("127.0.0.1", 9000), H).serve_forever()
'
```

Terminal 2 — the MCP server:

```bash
uv run cli2mcp serve examples/curl.tools.json -t streamable-http
```

Leave both running. All commands below run in a **third terminal**
(or just run the script: `./examples/debug_demo.sh`).

## 1. Initialize a session

Every MCP conversation starts with a handshake.

`examples/requests/1_initialize.json`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
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

## 2. Confirm the handshake

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
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -d @examples/requests/2_initialized.json
```

This is a notification (no `id` field), so the server returns an empty
HTTP 202 response.

## 3. List available tools

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

## 4. Call the tool to fetch a web page

`examples/requests/4_call_tool.json`:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "curl",
    "arguments": {
      "url": "http://127.0.0.1:9000"
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

Expected: `content[0].text` contains `Hello, world!`.

## What just happened

```
You (curl)  --->  MCP server (:8000)  --->  curl  --->  hello_server (:9000)
   HTTP POST       reads tools.json         subprocess     "Hello, world!"
   JSON-RPC        builds command            runs it        returned
```

1. Your curl sent a JSON-RPC `tools/call` to the MCP server over **Streamable HTTP**
2. The server looked up `curl` in `examples/curl.tools.json`
3. It built the command: `curl http://127.0.0.1:9000`
4. It ran it with `subprocess.run()`
5. It returned stdout (`Hello, world!`) as MCP tool output wrapped in an SSE `data:` line
