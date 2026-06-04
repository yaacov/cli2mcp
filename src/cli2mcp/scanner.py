"""Scan a CLI tool and produce a tools descriptor.

This module runs ``<command> --help``, parses the output, optionally
recurses into subcommands, and assembles a plain dictionary that can be
written to a JSON file.
"""

import json
import re
import subprocess
import sys

from cli2mcp.parser import parse_help


def _strip_man_formatting(text):
    """Remove man-page bold/underline sequences (char + backspace + char)."""
    return re.sub(r".\x08", "", text)


def _looks_like_man_page(text):
    """Return True if the text appears to be a rendered man page."""
    return "\x08" in text


def _run_help(command_parts):
    """Run a command with a help flag and return its output text.

    Tries ``-h`` first (short, parseable output) then ``--help``.
    If the output looks like a rendered man page, it is cleaned up
    and the short ``-h`` form is preferred.
    """
    results = {}
    for flag in ["-h", "--help"]:
        cmd = list(command_parts) + [flag]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
        except FileNotFoundError:
            print(f"Error: command not found: {cmd[0]}", file=sys.stderr)
            sys.exit(1)
        except subprocess.TimeoutExpired:
            continue

        output = result.stdout or result.stderr or ""
        if not output.strip():
            continue

        # If the output is clean (not a man page), use it immediately.
        if not _looks_like_man_page(output):
            return output

        # Store man-page output as fallback.
        results[flag] = _strip_man_formatting(output)

    # Return whatever we collected, preferring -h.
    return results.get("-h", results.get("--help", ""))


def scan(command):
    """Scan a CLI tool and return a tools descriptor dictionary.

    If the tool has subcommands, each subcommand becomes its own tool entry.
    Otherwise, the tool itself is the single entry.

    Returns::

        {
            "command": "git",
            "tools": [
                {
                    "name": "git_commit",
                    "description": "...",
                    "args": [...]
                },
                ...
            ]
        }
    """
    help_text = _run_help([command])
    parsed = parse_help(help_text)

    tools = []

    if parsed["subcommands"]:
        # One tool per subcommand.
        for sub in parsed["subcommands"]:
            sub_help = _run_help([command, sub])
            sub_parsed = parse_help(sub_help)
            tools.append({
                "name": f"{command}_{sub}",
                "description": sub_parsed["description"],
                "args": _format_args(sub_parsed["args"]),
            })
    else:
        # The command itself is the single tool.
        tools.append({
            "name": command,
            "description": parsed["description"],
            "args": _format_args(parsed["args"]),
        })

    return {"command": command, "tools": tools}


def _format_args(args):
    """Normalise argument dicts for the JSON output."""
    formatted = []
    for arg in args:
        formatted.append({
            "name": arg["name"],
            "description": arg["description"],
            "type": "string",
            "required": arg["required"],
        })
    return formatted


def save(tools_dict, path):
    """Write a tools descriptor dictionary to a JSON file."""
    with open(path, "w") as f:
        json.dump(tools_dict, f, indent=2)
    print(f"Wrote {path}")
