"""Command-line entry point for cli2mcp.

Usage::

    cli2mcp scan <command> [-o tools.json]
    cli2mcp serve <tools.json>
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="cli2mcp",
        description="Turn any CLI tool into an MCP server.",
    )
    subparsers = parser.add_subparsers(dest="action")

    # --- scan ---
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a CLI tool's --help and generate a tools JSON file.",
    )
    scan_parser.add_argument(
        "command",
        help="The CLI command to scan (e.g. git, curl, docker).",
    )
    scan_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output JSON file path (default: <command>.tools.json).",
    )

    # --- serve ---
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start an MCP server from a tools JSON file.",
    )
    serve_parser.add_argument(
        "tools_file",
        help="Path to the tools JSON file.",
    )
    serve_parser.add_argument(
        "-t", "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio).",
    )

    args = parser.parse_args()

    if args.action is None:
        parser.print_help()
        sys.exit(1)

    if args.action == "scan":
        from cli2mcp.scanner import scan, save

        output = args.output or f"{args.command}.tools.json"
        tools = scan(args.command)
        save(tools, output)

    elif args.action == "serve":
        import json
        import signal
        from cli2mcp.server import create_server

        with open(args.tools_file) as f:
            data = json.load(f)

        tool_count = len(data.get("tools", []))
        command = data.get("command", "unknown")

        print(f"cli2mcp server starting")
        print(f"  Command:   {command}")
        print(f"  Tools:     {tool_count}")
        print(f"  File:      {args.tools_file}")
        print(f"  Transport: {args.transport}")
        print()
        print("Press Ctrl+C to stop the server.")
        sys.stdout.flush()

        def _shutdown(signum, frame):
            print("\nShutting down.")
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        server = create_server(args.tools_file)
        server.run(transport=args.transport)
