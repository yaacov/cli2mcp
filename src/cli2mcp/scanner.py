"""Scan a CLI tool and produce a tools descriptor.

Runs '<command> -h', parses the output, recurses into subcommands,
and assembles a dictionary that can be written to JSON.
"""

import json
import subprocess
import sys

from cli2mcp.parser import parse_help


def _run_help(command_parts):
    """Run '<command> -h' and return the output text."""
    cmd = list(command_parts) + ["-h"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        print(f"Error: command not found: {cmd[0]}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        return ""

    return result.stdout or result.stderr or ""


def scan(command):
    """Scan a CLI tool and return a tools descriptor dictionary.

    If the tool has subcommands, each one becomes its own tool entry.
    Otherwise, the tool itself is the single entry.
    """
    help_text = _run_help([command])
    parsed = parse_help(help_text)

    tools = []

    if parsed["subcommands"]:
        for sub in parsed["subcommands"]:
            sub_help = _run_help([command, sub])
            sub_parsed = parse_help(sub_help)
            tools.append({
                "name": f"{command}_{sub}",
                "description": sub_parsed["description"],
                "args": _format_args(sub_parsed["args"]),
            })
    else:
        tools.append({
            "name": command,
            "description": parsed["description"],
            "args": _format_args(parsed["args"]),
        })

    return {"command": command, "tools": tools}


def _format_args(args):
    """Normalise argument dicts for the JSON output."""
    return [
        {
            "name": arg["name"],
            "description": arg["description"],
            "type": "string",
            "required": arg["required"],
        }
        for arg in args
    ]


def save(tools_dict, path):
    """Write a tools descriptor dictionary to a JSON file."""
    with open(path, "w") as f:
        json.dump(tools_dict, f, indent=2)
    print(f"Wrote {path}")
