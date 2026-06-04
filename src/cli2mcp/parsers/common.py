"""Shared helpers used by all parsers."""

import re


def make_description(description_lines, text):
    """Join description lines, or fall back to the command name from Usage."""
    if description_lines:
        return " ".join(description_lines)

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("usage"):
            # Capture "git commit" from "usage: git commit [-a] ..."
            match = re.match(r"[Uu]sage:\s*([\w][\w.-]*(?:\s+[\w][\w.-]*)*)", stripped)
            if match:
                return f"{match.group(1)} command"
    return ""


def extract_positional_args(text):
    """Extract positional args from the Usage line (e.g. <url>)."""
    args = []
    seen = set()

    for line in text.splitlines():
        if not line.strip().lower().startswith("usage"):
            continue

        for match in re.finditer(r"<(\w[\w-]*)>", line):
            name = match.group(1).lower()
            if name not in seen:
                args.append({
                    "name": name,
                    "description": name,
                    "required": True,
                })
                seen.add(name)

    return args
