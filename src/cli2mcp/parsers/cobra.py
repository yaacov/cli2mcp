"""Parser for Go Cobra style help text (kubectl, oc, docker, gh, ...).

Flags span two lines: name + default on line 1, description on line 2.
Subcommands are listed under category headers.

    Manage your cluster:
      get             Display one or many resources
      describe        Show details of a resource

    Options:
        --all-namespaces=false:
            If present, list across all namespaces.

        -o, --output='':
            Output format.  One of: json|yaml|wide|name.
"""

import re

from cli2mcp.parsers.common import extract_positional_args, make_description


def can_parse(text):
    """True if text has Cobra-style multi-line flags or the Cobra footer."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "=" in stripped and stripped.endswith(":"):
            return True
        if re.match(r'Use ".+ <command> --help"', stripped):
            return True
    return False


def parse(text):
    """Parse Cobra-style help using a state machine.

    States: description, options, subcommands, skip.
    The key pattern is "pending flag": when we see '--flag=default:',
    we store the name and read the next line as its description.
    """
    description_lines = []
    args = []
    subcommands = []
    state = "description"
    pending_flag = None

    for line in text.splitlines():
        # If the previous line was a flag header, this line is its description.
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

        header = _detect_header(line)
        if header is not None:
            if header == "options":
                state = "options"
            elif header in ("examples", "usage"):
                state = "skip"
            else:
                state = "subcommands"
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

        elif state == "options":
            flag_name = _parse_flag_header(line)
            if flag_name is not None:
                pending_flag = flag_name

        elif state == "subcommands":
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("-"):
                flag_name = _parse_flag_header(line)
                if flag_name is not None:
                    pending_flag = flag_name
            else:
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


def _parse_flag_header(line):
    """Parse '--output=default:' and return the flag name."""
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None

    match = re.match(
        r"(-\S+(?:,\s*-\S+)*)"  # flag name(s)
        r"(?:=\S*)?"             # optional default
        r":$",                   # trailing colon
        stripped,
    )
    if not match:
        return None

    flags = match.group(1)
    names = [f.strip() for f in flags.split(",")]
    return max(names, key=len)


def _parse_subcommand_line(line):
    """Parse '  get  Display one or many resources' into the name."""
    stripped = line.strip()
    if not stripped:
        return None
    match = re.match(r"(\w[\w-]*)\s{2,}(.+)", stripped)
    if match:
        return match.group(1)
    return None
