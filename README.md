# cli2mcp -- Turn any CLI into an MCP Server

An educational Python library that bridges the gap between traditional
command-line tools and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

**cli2mcp** scans a CLI tool's `--help` output, extracts its arguments and
subcommands, and generates a JSON descriptor file.  It can then serve that
file as a fully functional MCP server -- letting AI assistants call the CLI
tool through a standard protocol.

## Quick start

```bash
uv sync
```

### 1. Scan a CLI tool

```bash
uv run cli2mcp scan curl
```

This runs `curl --help`, parses the output, and writes `curl.tools.json`.

For tools with subcommands (like `git`):

```bash
uv run cli2mcp scan git -o git.tools.json
```

Each subcommand becomes its own MCP tool.

### 2. Serve as an MCP server

```bash
uv run cli2mcp serve curl.tools.json
```

This starts an MCP server (stdio transport) that exposes every entry in
the JSON file as a callable tool.

### 3. Connect to an AI assistant

Add the server to your assistant's MCP configuration.

```json
{
  "mcpServers": {
    "curl": {
      "command": "cli2mcp",
      "args": ["serve", "curl.tools.json"]
    }
  }
}
```

## How it works

```
                                        MCP client
                                            |
cli2mcp scan curl   -->  curl.tools.json    |
                              |             |
                         cli2mcp serve  <---+
                              |
                         subprocess.run(["curl", ...])
```

### The JSON schema

The generated file looks like this:

```json
{
  "command": "curl",
  "tools": [
    {
      "name": "curl",
      "description": "transfer a URL",
      "args": [
        {
          "name": "url",
          "description": "URL to transfer",
          "type": "string",
          "required": true
        },
        {
          "name": "--output",
          "description": "Write output to file instead of stdout",
          "type": "string",
          "required": false
        }
      ]
    }
  ]
}
```

- **`command`** -- the base CLI binary to run.
- **`tools`** -- one entry per tool (or per subcommand).
- **`args`** -- each argument has a `name`, `description`, `type` (always
  `"string"`), and `required` flag.
- Argument names starting with `--` are flags; others are positional.
- You can hand-edit this file to add, remove, or rename tools.

### How arguments map back to CLI commands

When the MCP server receives a tool call like:

```json
{"name": "git_commit", "arguments": {"message": "fix bug", "all": "true"}}
```

It reconstructs the CLI command:

```bash
git commit --message "fix bug" --all true
```

Flags (names starting with `--`) are emitted as `--flag value`.
Positional arguments are appended at the end.

## Supported help styles

Different CLI frameworks produce different `--help` formats.
cli2mcp auto-detects the style and uses the right parser:

| Style     | Frameworks              | Flag format                          |
|-----------|-------------------------|--------------------------------------|
| **GNU**   | argparse, click, GNU    | `--flag  description` (one line)     |
| **Cobra** | kubectl, oc, docker, gh | `--flag=default:` + next line        |
| **Plain** | curl, busybox           | flags listed without section headers |

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- `mcp[cli]` (the official MCP Python SDK, installed automatically)
