"""Parser for plain / minimal help text (curl, busybox, …).

Some tools print a compact help screen with no section headers at all.
Flags are listed directly after a ``Usage:`` line, and there are no
labelled sections like ``Options:`` or ``Commands:``.

**How to recognise it:**

The text starts with ``Usage:`` and the remaining lines are mostly
flag entries -- no section headers are present::

    Usage: curl [options...] <url>
     -d, --data <data>           HTTP POST data
     -f, --fail                  Fail fast with no output on HTTP errors
     -o, --output <file>         Write to file instead of stdout
     -v, --verbose               Make the operation more talkative

**Key characteristics:**
- No section headers at all (no "Options:", "Commands:", etc.)
- Flags start right after the usage line
- Each flag is a single line: ``-x, --long   description``
- Subcommands are rare but possible (listed as ``word  description``)
"""

import re

from cli2mcp.parsers.common import extract_positional_args


def can_parse(text):
    """Return True if *text* looks like plain/headerless help.

    We check that the text contains flag-like lines (starting with ``-``)
    but does *not* contain any standard section headers.  This makes it
    the "catch-all" parser for simple tools.
    """
    has_flags = False
    has_headers = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "  " in stripped:
            has_flags = True
        # Check for section headers (flush-left, ending with ":")
        if (stripped.endswith(":") and not stripped.startswith("-")
                and len(line) - len(line.lstrip()) <= 4):
            name = stripped[:-1].strip().lower()
            if name in ("options", "commands", "positional arguments",
                        "optional arguments", "subcommands", "flags"):
                has_headers = True

    # Plain style: has flags but no standard section headers.
    return has_flags and not has_headers


def parse(text):
    """Parse plain-style help text into a structured dict.

    Returns::

        {
            "description": "...",
            "args": [...],
            "subcommands": [...]
        }

    **How it works:**

    Since there are no section headers, the approach is simpler than
    the GNU or Cobra parsers:

    1. Collect description lines from the top (before "Usage:").
    2. After the usage line, scan every remaining line:
       - If it starts with ``-``, try to parse it as a flag.
       - Otherwise, try to parse it as a subcommand.
    3. That's it -- no state machine needed.
    """
    lines = text.splitlines()
    description_lines = []
    args = []
    subcommands = []
    past_usage = False

    for line in lines:
        stripped = line.strip()

        # Collect description text before the usage line.
        if not past_usage:
            if stripped.lower().startswith("usage"):
                past_usage = True
                continue
            if stripped:
                description_lines.append(stripped)
            continue

        # After the usage line, classify each line.
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

    # Extract positional args from the usage line (e.g. <url>, PATTERN).
    positional = extract_positional_args(text)
    args.extend(positional)

    return {
        "description": " ".join(description_lines),
        "args": args,
        "subcommands": subcommands,
    }


# ---- Helpers --------------------------------------------------------


def _parse_flag_line(stripped):
    """Extract a flag from a single line.

    Expected format::

        -d, --data <data>      HTTP POST data
        -v, --verbose          Make the operation more talkative

    We pick the longest flag name (``--data`` over ``-d``).
    """
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
    """Extract a subcommand name from ``word   description``."""
    match = re.match(r"(\w[\w-]*)\s{2,}(.+)", stripped)
    if match:
        return match.group(1)
    return None
