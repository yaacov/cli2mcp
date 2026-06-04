"""Help-text parsers for different CLI styles.

Each module in this package handles one common help format:

- ``gnu``   -- GNU / Python argparse style (single-line flags, section headers)
- ``cobra`` -- Go Cobra style used by kubectl, oc, docker (multi-line flags)
- ``plain`` -- Minimal / headerless style used by curl and simple tools

Every parser exposes two functions:

    can_parse(text) -> bool
        Return True if this parser can handle the given help text.

    parse(text) -> dict
        Parse the text and return {"description", "args", "subcommands"}.

The main ``parser`` module auto-detects the style and delegates.
"""

from cli2mcp.parsers.gnu import can_parse as gnu_can_parse, parse as gnu_parse
from cli2mcp.parsers.cobra import can_parse as cobra_can_parse, parse as cobra_parse
from cli2mcp.parsers.plain import can_parse as plain_can_parse, parse as plain_parse

__all__ = [
    "gnu_can_parse", "gnu_parse",
    "cobra_can_parse", "cobra_parse",
    "plain_can_parse", "plain_parse",
]
