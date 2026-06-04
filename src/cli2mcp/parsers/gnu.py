"""Parser for GNU / Python argparse style help text.

This is the most common format for tools written in Python (argparse, click)
and C tools that follow the GNU conventions.

**How to recognise it:**

The help text has clearly labelled section headers like ``Options:``,
``Positional arguments:``, or ``Commands:`` -- each ending with a colon
at the start of a line.  Flags and their descriptions sit on the *same*
line, separated by a gap of two or more spaces::

    usage: mytool [-v] [-o FILE] filename

    My awesome tool for processing files.

    Positional arguments:
      filename          The file to process

    Options:
      -v, --verbose     Enable verbose output
      -o, --output FILE Output file path
      -h, --help        Show this message and exit

    Commands:
      run               Run the tool
      check             Check the input

**Key characteristics:**
- Section headers are flush-left (or lightly indented) lines ending with ``:``
- Each flag/argument is a *single line*: name(s), gap, description
- Subcommands (if any) appear under a "Commands:" or similar header
"""

import re

from cli2mcp.parsers.common import extract_positional_args

# Section header names we understand (lowercased).
_POSITIONAL_HEADERS = {"positional arguments", "positional"}
_OPTION_HEADERS = {"options", "optional arguments", "flags"}
_SUBCOMMAND_HEADERS = {"commands", "subcommands", "available commands"}


def can_parse(text):
    """Return True if *text* looks like GNU / argparse style help.

    We look for at least one recognisable section header ("Options:",
    "Positional arguments:", etc.) at the start of a line.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.endswith(":") or stripped.startswith("-"):
            continue
        name = stripped[:-1].strip().lower()
        if name in _POSITIONAL_HEADERS | _OPTION_HEADERS | _SUBCOMMAND_HEADERS:
            return True
    return False


def parse(text):
    """Parse GNU-style help text into a structured dict.

    Returns::

        {
            "description": "My awesome tool ...",
            "args": [
                {"name": "--verbose", "description": "...", "required": False},
                {"name": "filename",  "description": "...", "required": True},
            ],
            "subcommands": ["run", "check"]
        }

    **How the state machine works:**

    We walk through the text line by line, keeping track of which
    "section" we are in.  When we see a header like ``Options:``, we
    switch to the corresponding state and start collecting entries.

    States:
        description  -- before any section header; collect description text
        positional   -- inside "Positional arguments:" section
        options      -- inside "Options:" section
        subcommands  -- inside "Commands:" section
        skip         -- inside an unrecognised section; ignore lines
    """
    lines = text.splitlines()
    description_lines = []
    args = []
    subcommands = []

    state = "description"

    for line in lines:
        # --- Detect section headers ---
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

        # --- Act based on current state ---

        if state == "description":
            stripped = line.strip()
            # A "usage:" line ends the description.
            if stripped.lower().startswith("usage"):
                state = "skip"
                continue
            if stripped:
                description_lines.append(stripped)
            elif description_lines:
                # First blank line after text ends the description.
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

    # Extract positional args from the usage line (e.g. <url>, PATTERN).
    positional = extract_positional_args(text)
    args.extend(positional)

    return {
        "description": " ".join(description_lines),
        "args": args,
        "subcommands": subcommands,
    }


# ---- Helpers --------------------------------------------------------


def _detect_header(line):
    """Return the section name if *line* is a section header, else None.

    A section header is a line that:
    - ends with ``:``
    - is not deeply indented (at most 4 leading spaces)
    - does not start with ``-`` (that would be a flag)
    """
    stripped = line.strip()
    if not stripped.endswith(":") or stripped.startswith("-"):
        return None
    leading_spaces = len(line) - len(line.lstrip())
    if leading_spaces > 4:
        return None
    return stripped[:-1].strip().lower()


def _parse_flag_line(line):
    """Extract a flag or positional argument from a single help line.

    Matches two patterns:

    1. Flag with description::

           -v, --verbose       Enable verbose output
           --output FILE       Output file path

    2. Positional argument::

           filename            The file to process

    The flag name and description are separated by 2+ spaces.
    When both short and long forms exist, we keep the longest name.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("---"):
        return None

    # Pattern 1: flag(s) [METAVAR]  description
    flag_match = re.match(
        r"(-\S+(?:,\s*-\S+)*)"  # one or more flags: -v, --verbose
        r"(?:\s+\S+)?"          # optional metavar:  FILE, VALUE, …
        r"\s{2,}"               # gap (at least two spaces)
        r"(.+)",                # description
        stripped,
    )
    if flag_match:
        flags = flag_match.group(1)
        description = flag_match.group(2).strip()
        names = [f.strip() for f in flags.split(",")]
        name = max(names, key=len)
        return {"name": name, "description": description, "required": False}

    # Pattern 2: word  description  (positional argument)
    pos_match = re.match(
        r"(\w[\w-]*)"  # argument name
        r"\s{2,}"      # gap
        r"(.+)",       # description
        stripped,
    )
    if pos_match:
        return {
            "name": pos_match.group(1),
            "description": pos_match.group(2).strip(),
            "required": True,
        }

    return None


def _parse_subcommand_line(line):
    """Extract a subcommand name from an indented help line.

    Matches::

        commit           Record changes to the repository

    Also handles brace-lists::

        {cmd1,cmd2}      Available subcommands

    Returns the subcommand name string, or None.
    """
    stripped = line.strip()
    if not stripped:
        return None

    match = re.match(r"(\w[\w-]*)\s{2,}(.+)", stripped)
    if match:
        return match.group(1)

    brace_match = re.match(r"\{(.+)\}", stripped)
    if brace_match:
        # Return first one; the caller can re-parse if needed.
        names = [s.strip() for s in brace_match.group(1).split(",") if s.strip()]
        return names[0] if names else None

    return None
