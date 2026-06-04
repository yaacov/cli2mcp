"""Shared helpers used by all parsers.

This module contains utilities that are not specific to any one help
style.  Right now it has one function: extracting positional arguments
from the ``Usage:`` line.
"""

import re


def extract_positional_args(text):
    """Extract positional argument names from usage lines.

    Most CLI tools show positional arguments on the usage line::

        Usage: curl [options...] <url>
        Usage: rg [OPTIONS] PATTERN [PATH ...]
        Usage: cp SOURCE DEST

    We recognise two conventions:

    1. **Angle brackets**: ``<url>``, ``<file>``, ``<pattern>``
    2. **UPPERCASE words**: ``PATTERN``, ``SOURCE``, ``DEST``

    We skip common noise like ``[options...]``, ``[OPTIONS]``, ``[flags]``,
    and the command name itself.

    Returns a list of dicts::

        [{"name": "url", "description": "url", "required": True}, ...]
    """
    args = []
    seen = set()

    for line in text.splitlines():
        stripped = line.strip().lower()
        if not stripped.startswith("usage"):
            continue

        # Work on the original (not lowered) line to preserve case.
        original = line.strip()

        # Pattern 1: angle-bracket args like <url>, <file>
        for match in re.finditer(r"<(\w[\w-]*)>", original):
            name = match.group(1).lower()
            if name not in seen:
                args.append({
                    "name": name,
                    "description": name,
                    "required": True,
                })
                seen.add(name)

        # Pattern 2: UPPERCASE positional args like PATTERN, SOURCE
        # Skip known noise words.
        noise = {"usage", "options", "opts", "flags", "command", "args",
                 "subcommand", "http"}
        for match in re.finditer(r"\b([A-Z][A-Z_-]{1,})\b", original):
            name = match.group(1).lower()
            if name not in noise and name not in seen:
                args.append({
                    "name": name,
                    "description": name,
                    "required": True,
                })
                seen.add(name)

    return args
