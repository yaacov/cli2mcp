"""Parser for Go Cobra style help text (kubectl, oc, docker, gh, …).

Cobra is the most popular CLI framework in Go.  Tools built with it --
including kubectl, oc, docker, and gh -- share a distinctive help format.

**How to recognise it:**

Flags and their descriptions are on *separate* lines.  The flag line
shows the name and a default value, ending with a colon.  The description
follows on the next line, indented with a tab::

    Options:
        --all-namespaces=false:
    	    If present, list across all namespaces.

        -o, --output='':
    	    Output format.  One of: json|yaml|wide|name.

Subcommands are listed under category headers like "Basic Commands:" or
"Troubleshooting and Debugging Commands:" -- these headers don't match
any standard keyword, but the indented entries underneath look the same
as GNU-style subcommands::

    Basic Commands:
      create          Create a resource from a file or stdin
      get             Display one or many resources

**Key characteristics compared to GNU style:**
- Flags span **two lines**: name+default on line 1, description on line 2
- Flag lines end with ``=<default>:`` (e.g. ``=false:``, ``='':``)
- The ``Usage:`` line appears at the *bottom*, not the top
- Category headers are free-form text (not just "Options:")
"""

import re

from cli2mcp.parsers.common import extract_positional_args


def can_parse(text):
    """Return True if *text* looks like Cobra-style help.

    We look for two possible signals:

    1. **Subcommand-level help**: contains multi-line flag entries --
       a line starting with ``-``, containing ``=``, ending with ``:``.
       For example: ``    --output='':`` or ``    -n, --namespace='':``

    2. **Top-level help**: ends with the Cobra signature line
       ``Use "<cmd> <command> --help" for more information``.
       This pattern is unique to Cobra-generated CLI tools.
    """
    for line in text.splitlines():
        stripped = line.strip()
        # Signal 1: multi-line flag header
        if stripped.startswith("-") and "=" in stripped and stripped.endswith(":"):
            return True
        # Signal 2: Cobra footer telling users how to get subcommand help
        if re.match(r'Use ".+ <command> --help"', stripped):
            return True
    return False


def parse(text):
    """Parse Cobra-style help text into a structured dict.

    Returns the same shape as the other parsers::

        {
            "description": "...",
            "args": [...],
            "subcommands": [...]
        }

    **How it works:**

    We walk through the lines with a simple state machine:

    1. **Description phase**: collect non-empty lines at the top until we
       hit a blank line or a section header.

    2. **Section handling**: when we see a header ending with ``:``, we
       check whether the content below it contains flags (Cobra-style
       multi-line entries) or subcommands (``word  description`` entries).

    3. **Multi-line flags**: when a line matches the pattern
       ``--flag=default:``, we store the flag name and read the
       *next* line as the description.  This "pending flag" mechanism
       is the key difference from the GNU parser.

    4. **Subcommands**: non-flag indented lines that match
       ``word   description`` are treated as subcommand entries.

    5. We skip sections we don't understand (Examples, Usage, etc.).
    """
    lines = text.splitlines()
    description_lines = []
    args = []
    subcommands = []

    state = "description"
    pending_flag = None  # holds flag name while we wait for its description

    for line in lines:
        # --- Multi-line flag continuation ---
        # If the *previous* line was a flag header (e.g. "--output='':"),
        # this line is its description.
        if pending_flag is not None:
            desc = line.strip()
            if desc:
                args.append({
                    "name": pending_flag,
                    "description": desc,
                    "required": False,
                })
            pending_flag = None
            continue

        # --- Section header detection ---
        header = _detect_header(line)
        if header is not None:
            if header == "options":
                state = "options"
            elif header in ("examples", "usage"):
                state = "skip"
            else:
                # Category headers like "Basic Commands:" or
                # "Troubleshooting and Debugging Commands:" --
                # content could be subcommands or more flags.
                state = "auto"
            continue

        # --- Act based on current state ---

        if state == "description":
            stripped = line.strip()
            if stripped.lower().startswith("usage"):
                state = "skip"
                continue
            if stripped:
                description_lines.append(stripped)
            elif description_lines:
                state = "auto"

        elif state == "options":
            # Try the Cobra multi-line flag pattern first.
            flag_name = _parse_flag_header(line)
            if flag_name is not None:
                pending_flag = flag_name
                continue

            # Fall back to single-line flags (some Cobra tools mix styles).
            arg = _parse_single_line_flag(line)
            if arg is not None:
                arg["required"] = False
                args.append(arg)

        elif state == "auto":
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("-"):
                # Looks like a flag.
                flag_name = _parse_flag_header(line)
                if flag_name is not None:
                    pending_flag = flag_name
                else:
                    arg = _parse_single_line_flag(line)
                    if arg is not None:
                        arg["required"] = False
                        args.append(arg)
            else:
                # Non-flag line -- try as subcommand.
                name = _parse_subcommand_line(line)
                if name is not None:
                    subcommands.append(name)

        # state == "skip": do nothing

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
    """Return a normalised header name, or None.

    Cobra headers are flush-left (or lightly indented) lines ending
    with ``:``.  We normalise to lowercase for easy comparison.

    We reject deeply-indented lines (>4 spaces) because those are
    flag definitions like ``    --output='':`` -- not headers.
    """
    stripped = line.strip()
    if not stripped.endswith(":") or stripped.startswith("-"):
        return None
    leading_spaces = len(line) - len(line.lstrip())
    if leading_spaces > 4:
        return None
    return stripped[:-1].strip().lower()


def _parse_flag_header(line):
    """Extract a flag name from a Cobra-style multi-line flag header.

    The flag header has the format::

        -c, --container='':
        --all-namespaces=false:
        --chunk-size=500:

    The name is followed by ``=<default>`` and a trailing colon.
    The description will come on the *next* line, so we only return
    the flag name here.

    When both short and long forms exist (``-c, --container``),
    we keep the longest name.
    """
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None

    match = re.match(
        r"(-\S+(?:,\s*-\S+)*)"  # flag name(s)
        r"(?:=\S*)?"             # optional default value
        r":$",                   # trailing colon
        stripped,
    )
    if not match:
        return None

    flags = match.group(1)
    names = [f.strip() for f in flags.split(",")]
    return max(names, key=len)


def _parse_single_line_flag(line):
    """Fall back: try to parse a GNU-style single-line flag.

    Some Cobra tools mix styles, so we handle this as a safety net.
    """
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None

    match = re.match(
        r"(-\S+(?:,\s*-\S+)*)"
        r"(?:\s+\S+)?"
        r"\s{2,}"
        r"(.+)",
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
    """Extract a subcommand name from an indented line.

    Same format as GNU style::

        get             Display one or many resources
    """
    stripped = line.strip()
    if not stripped:
        return None

    match = re.match(r"(\w[\w-]*)\s{2,}(.+)", stripped)
    if match:
        return match.group(1)

    return None
