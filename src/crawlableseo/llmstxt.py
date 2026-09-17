"""llms.txt: a plain-language map of the site for models and agents.

The format is Markdown by convention: an H1 with the site's name, a
blockquote summarising it in one paragraph, then sections of links with a
sentence each. Keep it honest and specific; a model quoting this file will
quote whatever it says, including the parts that oversell.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmsSection:
    title: str
    links: Sequence[tuple[str, str, str]]
    """``(label, url, one-line description)`` per link."""


def llms_txt(
    name: str,
    summary: str,
    sections: Iterable[LlmsSection],
    *,
    notes: Sequence[str] = (),
) -> str:
    out = [f"# {name}", "", f"> {summary}", ""]
    for note in notes:
        out += [note, ""]
    for section in sections:
        out.append(f"## {section.title}")
        out.append("")
        for label, url, description in section.links:
            out.append(f"- [{label}]({url}): {description}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
