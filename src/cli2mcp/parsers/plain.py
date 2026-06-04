"""Parser for plain / minimal help text (curl, busybox, ...).

These tools print flags directly after a Usage: line with no
section headers like "Options:" or "Commands:".

    Usage: curl [options...] <url>
     -d, --data <data>           HTTP POST data
     -f, --fail                  Fail fast with no output on HTTP errors
"""

import re

from cli2mcp.parsers.common import extract_positional_args, make_description


def can_parse(text):
    """True if text has flag lines but no section headers."""
    has_flags = False
    has_headers = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "  " in stripped:
            has_flags = True
        if (stripped.endswith(":") and not stripped.startswith("-")
                and len(line) - len(line.lstrip()) <= 4):
            name = stripped[:-1].strip().lower()
            if name in ("options", "commands", "positional arguments",
                        "optional arguments", "subcommands", "flags"):
                has_headers = True

    return has_flags and not has_headers


def parse(text):
    """Parse plain-style help text.

    1. Collect description lines before "Usage:"
    2. After Usage:, parse "-" lines as flags and "word  desc" as subcommands
    """
    description_lines = []
    args = []
    subcommands = []
    past_usage = False

    for line in text.splitlines():
        stripped = line.strip()

        if not past_usage:
            if stripped.lower().startswith("usage"):
                past_usage = True
                continue
            if stripped:
                description_lines.append(stripped)
            continue

        if not stripped:
            continue

        if stripped.startswith("-"):
            arg = _parse_flag_line(stripped)
            if arg is not None:
                args.append(arg)
        else:
            name = _parse_subcommand_line(stripped)
            if name is not None:
                subcommands.append(name)

    args.extend(extract_positional_args(text))

    return {
        "description": make_description(description_lines, text),
        "args": args,
        "subcommands": subcommands,
    }


def _parse_flag_line(stripped):
    """Parse '-d, --data <data>  HTTP POST data' into a dict."""
    match = re.match(
        r"(-\S+(?:,\s*-\S+)*)"  # flag name(s)
        r"(?:\s+\S+)?"          # optional metavar
        r"\s{2,}"               # gap
        r"(.+)",                # description
        stripped,
    )
    if match:
        flags = match.group(1)
        names = [f.strip() for f in flags.split(",")]
        return {
            "name": max(names, key=len),
            "description": match.group(2).strip(),
            "required": False,
        }
    return None


def _parse_subcommand_line(stripped):
    """Parse '  clone  Clone a repository' into the subcommand name."""
    match = re.match(r"(\w[\w-]*)\s{2,}(.+)", stripped)
    if match:
        return match.group(1)
    return None
