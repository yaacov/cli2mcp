"""Parser for GNU / Python argparse style help text.

These tools have section headers like "Options:" and "Commands:".
Flags and descriptions sit on the same line:

    usage: mytool [-v] [-o FILE] filename

    My awesome tool for processing files.

    Options:
      -v, --verbose     Enable verbose output
      -o, --output FILE Output file path

    Commands:
      run               Run the tool
      check             Check the input
"""

import re

from cli2mcp.parsers.common import extract_positional_args, make_description

_POSITIONAL_HEADERS = {"positional arguments", "positional"}
_OPTION_HEADERS = {"options", "optional arguments", "flags"}
_SUBCOMMAND_HEADERS = {"commands", "subcommands", "available commands"}


def can_parse(text):
    """True if text has at least one known section header."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.endswith(":") or stripped.startswith("-"):
            continue
        name = stripped[:-1].strip().lower()
        if name in _POSITIONAL_HEADERS | _OPTION_HEADERS | _SUBCOMMAND_HEADERS:
            return True
    return False


def parse(text):
    """Parse GNU-style help using a simple state machine.

    States: description, positional, options, subcommands, skip.
    Transitions happen when we hit a section header.
    """
    description_lines = []
    args = []
    subcommands = []
    state = "description"

    for line in text.splitlines():
        header = _detect_header(line)
        if header is not None:
            if header in _POSITIONAL_HEADERS:
                state = "positional"
            elif header in _OPTION_HEADERS:
                state = "options"
            elif header in _SUBCOMMAND_HEADERS:
                state = "subcommands"
            else:
                state = "skip"
            continue

        if state == "description":
            stripped = line.strip()
            if stripped.lower().startswith("usage"):
                state = "skip"
                continue
            if stripped:
                description_lines.append(stripped)
            elif description_lines:
                state = "skip"

        elif state == "positional":
            arg = _parse_flag_line(line)
            if arg is not None:
                arg["required"] = True
                args.append(arg)

        elif state == "options":
            arg = _parse_flag_line(line)
            if arg is not None:
                arg["required"] = False
                args.append(arg)

        elif state == "subcommands":
            name = _parse_subcommand_line(line)
            if name is not None:
                subcommands.append(name)

    args.extend(extract_positional_args(text))

    return {
        "description": make_description(description_lines, text),
        "args": args,
        "subcommands": subcommands,
    }


def _detect_header(line):
    """Return section name if line is a header like 'Options:', else None."""
    stripped = line.strip()
    if not stripped.endswith(":") or stripped.startswith("-"):
        return None
    if len(line) - len(line.lstrip()) > 4:
        return None
    return stripped[:-1].strip().lower()


def _parse_flag_line(line):
    """Parse '-v, --verbose  Enable verbose output' into a dict."""
    stripped = line.strip()
    if not stripped or stripped.startswith("---"):
        return None

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


def _parse_subcommand_line(line):
    """Parse '  commit  Record changes' into the subcommand name."""
    stripped = line.strip()
    if not stripped:
        return None
    match = re.match(r"(\w[\w-]*)\s{2,}(.+)", stripped)
    if match:
        return match.group(1)
    return None
