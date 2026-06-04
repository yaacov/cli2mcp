"""Auto-detect CLI help style and parse it.

Different CLI frameworks produce different ``--help`` formats.  This
module detects which style a given help text uses and delegates to the
right parser.

We support three styles:

=============  =====================  ==============================
Style          Framework examples     How flags look
=============  =====================  ==============================
**GNU**        argparse, click, GNU   ``--flag  description`` (one line)
**Cobra**      kubectl, oc, docker    ``--flag=default:`` + next line
**Plain**      curl, busybox          flags listed without headers
=============  =====================  ==============================

See the ``parsers/`` package for the individual implementations.

**Detection order matters.**  We try Cobra first because its multi-line
flag format is the most distinctive.  Then GNU, which requires standard
section headers.  Finally Plain, which is the catch-all for everything else.
"""

from cli2mcp.parsers.cobra import can_parse as _is_cobra, parse as _parse_cobra
from cli2mcp.parsers.gnu import can_parse as _is_gnu, parse as _parse_gnu
from cli2mcp.parsers.plain import parse as _parse_plain

# Detection order: most specific first, catch-all last.
_PARSERS = [
    ("cobra", _is_cobra, _parse_cobra),
    ("gnu",   _is_gnu,   _parse_gnu),
]


def detect_style(text):
    """Identify which help-text style *text* uses.

    Returns one of: ``"cobra"``, ``"gnu"``, or ``"plain"``.

    This is useful for debugging -- you can call it to see which
    parser cli2mcp will choose for a given tool.
    """
    for name, can_parse, _ in _PARSERS:
        if can_parse(text):
            return name
    return "plain"


def parse_help(text):
    """Parse a ``--help`` output string into a structured dictionary.

    Auto-detects the help style and delegates to the matching parser.

    Returns::

        {
            "description": "...",
            "args": [
                {"name": "--verbose", "description": "...", "required": False},
                {"name": "filename",  "description": "...", "required": True},
            ],
            "subcommands": ["commit", "push", ...]
        }
    """
    for _, can_parse, parse_fn in _PARSERS:
        if can_parse(text):
            return parse_fn(text)

    # Nothing matched -- fall back to the plain parser.
    return _parse_plain(text)
