"""MCP server that exposes CLI tools described in a JSON file.

This module loads a ``tools.json`` file produced by the scanner, registers
every tool entry with FastMCP, and -- when a tool is called -- translates
the MCP arguments back into a CLI command and runs it.

**The core challenge:**

FastMCP inspects Python function *signatures* to build the JSON Schema
that tells MCP clients which parameters a tool accepts.  But our tools
are defined at runtime (from JSON), not at coding time.  So we
dynamically build a function whose signature matches the args listed in
the JSON -- giving FastMCP the type information it needs.
"""

import inspect
import json
import subprocess

from mcp.server.fastmcp import FastMCP


def _to_param_name(arg_name):
    """Convert a CLI arg name to a valid Python parameter name.

    Strips leading dashes and replaces hyphens with underscores,
    because Python identifiers cannot contain hyphens::

        "--upload-file"  ->  "upload_file"
        "pathspec"       ->  "pathspec"
        "-v"             ->  "v"
    """
    return arg_name.lstrip("-").replace("-", "_")


def _build_command(base_command, tool, call_args):
    """Turn MCP tool-call arguments back into a CLI command list.

    Flags (args whose name starts with ``-``) are emitted as
    ``--flag value`` pairs.  Positional args are appended at the end
    in the order they appear in the tool definition.

    Example::

        tool  = {"name": "git_commit", "args": [
            {"name": "--message", ...},
            {"name": "pathspec", ...},
        ]}
        call_args = {"message": "fix bug", "pathspec": "main.py"}

        result = ["git", "commit", "--message", "fix bug", "main.py"]
    """
    cmd = [base_command]

    # Derive subcommand from tool name (e.g. "git_commit" -> "commit").
    prefix = base_command + "_"
    if tool["name"].startswith(prefix):
        subcommand = tool["name"][len(prefix):]
        cmd.append(subcommand)

    positionals = []

    for arg_def in tool["args"]:
        arg_name = arg_def["name"]              # e.g. "--upload-file"
        key = _to_param_name(arg_name)          # e.g. "upload_file"

        if key not in call_args:
            continue

        value = str(call_args[key])

        if arg_name.startswith("-"):
            cmd.extend([arg_name, value])
        else:
            positionals.append(value)

    cmd.extend(positionals)
    return cmd


def _make_handler(base_command, tool):
    """Build an async handler function with a proper signature.

    FastMCP reads the function's parameter list to generate the tool's
    JSON Schema.  A plain ``**kwargs`` handler would produce a useless
    schema.  Instead, we create a function whose parameters match the
    args defined in the JSON file.

    For example, if the JSON says the tool has args ``--output`` and
    ``url``, we produce a function equivalent to::

        async def curl(output: str = "", url: str = "") -> str:
            ...

    We use ``inspect.Parameter`` to build the signature dynamically.
    """
    tool_args = tool["args"]

    # Build the parameter list from the JSON args.
    params = []
    for arg_def in tool_args:
        key = _to_param_name(arg_def["name"])
        if arg_def.get("required"):
            # Required args have no default value.
            param = inspect.Parameter(
                key, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
            )
        else:
            # Optional args default to empty string.
            param = inspect.Parameter(
                key, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default="", annotation=str,
            )
        params.append(param)

    # The actual handler that runs the CLI command.
    async def handler(**kwargs):
        # Remove args the caller left at their default (empty string).
        call_args = {k: v for k, v in kwargs.items() if v != ""}
        cmd = _build_command(base_command, tool, call_args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout
        if result.returncode != 0:
            output += result.stderr
        return output or "(no output)"

    # Attach the proper signature so FastMCP can inspect it.
    handler.__signature__ = inspect.Signature(params)
    handler.__name__ = tool["name"]
    handler.__doc__ = tool["description"]

    return handler


def create_server(tools_file):
    """Create a FastMCP server from a tools JSON file.

    Reads the JSON, then registers one MCP tool per entry.  Each tool,
    when called, translates the MCP arguments back into a CLI command
    and runs it with ``subprocess.run()``.

    Returns the FastMCP server instance (call ``.run()`` to start it).
    """
    with open(tools_file) as f:
        data = json.load(f)

    base_command = data["command"]
    server = FastMCP(base_command)

    for tool in data["tools"]:
        handler = _make_handler(base_command, tool)
        server.add_tool(
            handler,
            name=tool["name"],
            description=tool["description"],
        )

    return server
