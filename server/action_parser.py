"""Robust parser for data cleaning commands."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedAction:
    command_type: str  # "inspect", "fix", "delete", "submit", "error"
    args: dict
    error_message: Optional[str] = None


# Strip markdown code fences and leading "action:" prefixes
_PREFIX_RE = re.compile(
    r"^(?:```\w*\s*\n?|action\s*[:\-]\s*|next\s*action\s*[:\-]\s*)",
    re.IGNORECASE,
)
_SUFFIX_RE = re.compile(r"\s*```\s*$")


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def parse_action(raw: str) -> ParsedAction:
    """Parse a raw command string into a structured ParsedAction."""
    if not raw or not raw.strip():
        return ParsedAction("error", {}, "Empty command. Use inspect/fix/delete/submit.")

    text = raw.strip()
    text = _PREFIX_RE.sub("", text)
    text = _SUFFIX_RE.sub("", text)
    text = text.strip()

    # Try each command pattern
    for parser in [_parse_submit, _parse_inspect, _parse_delete, _parse_fix]:
        result = parser(text)
        if result is not None:
            return result

    return ParsedAction(
        "error",
        {},
        f"Could not parse: '{raw.strip()[:80]}'. "
        "Expected: inspect(\"col\"), fix(row, \"col\", \"val\"), delete(row), or submit()",
    )


def _parse_submit(text: str) -> Optional[ParsedAction]:
    if re.match(r"^submit\s*(\(\s*\))?\s*$", text, re.IGNORECASE):
        return ParsedAction("submit", {})
    return None


def _parse_inspect(text: str) -> Optional[ParsedAction]:
    m = re.match(
        r'^inspect\s*\(\s*(["\']?)(\w+)\1\s*\)$', text, re.IGNORECASE
    )
    if m:
        return ParsedAction("inspect", {"column": m.group(2)})
    return None


def _parse_delete(text: str) -> Optional[ParsedAction]:
    m = re.match(r"^delete\s*\(\s*(\d+)\s*\)$", text, re.IGNORECASE)
    if m:
        return ParsedAction("delete", {"row": int(m.group(1))})
    return None


def _parse_fix(text: str) -> Optional[ParsedAction]:
    # fix(row, "column", "value") — value may contain commas, quotes, parens
    # Strategy: match the row and column greedily, then take everything else as value
    m = re.match(
        r'^fix\s*\(\s*(\d+)\s*,\s*(["\']?)(\w+)\2\s*,\s*(.+)\)$',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        row = int(m.group(1))
        column = m.group(3)
        value = _strip_quotes(m.group(4).strip())
        return ParsedAction("fix", {"row": row, "column": column, "value": value})

    # Fallback: more permissive pattern for LLMs that format differently
    m = re.match(
        r'^fix\s*\(\s*row\s*=\s*(\d+)\s*,\s*(?:column|col)\s*=\s*(["\']?)(\w+)\2\s*,\s*(?:value|val)\s*=\s*(.+)\)$',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        row = int(m.group(1))
        column = m.group(3)
        value = _strip_quotes(m.group(4).strip())
        return ParsedAction("fix", {"row": row, "column": column, "value": value})

    return None
