"""Auto-detect CLI help style and delegate to the right parser.

Detection order: Cobra first (most distinctive), then GNU, then Plain
(catch-all).
"""

from cli2mcp.parsers.cobra import can_parse as _is_cobra, parse as _parse_cobra
from cli2mcp.parsers.gnu import can_parse as _is_gnu, parse as _parse_gnu
from cli2mcp.parsers.plain import parse as _parse_plain

_PARSERS = [
    ("cobra", _is_cobra, _parse_cobra),
    ("gnu",   _is_gnu,   _parse_gnu),
]


def detect_style(text):
    """Return 'cobra', 'gnu', or 'plain'."""
    for name, can_parse, _ in _PARSERS:
        if can_parse(text):
            return name
    return "plain"


def parse_help(text):
    """Parse --help output into {description, args, subcommands}."""
    for _, can_parse, parse_fn in _PARSERS:
        if can_parse(text):
            return parse_fn(text)
    return _parse_plain(text)
