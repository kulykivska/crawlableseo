"""Read an llms.txt back and say what is wrong with it.

The format is young, so this is strict about structure - a model reading the
file has to find the map without guessing - and advisory about everything
else. Errors mean the file is not an llms.txt. Warnings mean it is, and it
will serve a model badly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ERROR = "error"
WARNING = "warning"

# "- [label](url): description". The spec says a colon; files in the wild use a
# dash just as often, and the link is what matters. Only at the left margin: an
# indented bullet is detail under the link above it.
LINK = re.compile(
    r"^[-*]\s+\[(?P<label>[^\]]*)\]\((?P<url>[^)]*)\)\s*[:\-\u2013\u2014]?\s*(?P<desc>.*)$"
)
BULLET = re.compile(r"^[-*]\s+")
# A wrapped line: the description of the link above, continued.
CONTINUATION = re.compile(r"^\s+\S")
HEADING = re.compile(r"^(?P<hashes>#{1,6})\s*(?P<text>.*)$")

# The section the spec sets aside for links a model may skip. It says what may
# be dropped when context runs short, which only works if it is last.
OPTIONAL = "optional"


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    line: int
    message: str

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line else "file"
        return f"{where}: {self.level} [{self.code}] {self.message}"


def check_llms_txt(text: str) -> list[Finding]:
    """Every problem in one pass, in the order they appear in the file."""
    findings: list[Finding] = []
    lines = text.splitlines()
    if not text.strip():
        return [Finding(ERROR, "E_EMPTY", 0, "the file is empty")]

    first = next((i for i, line in enumerate(lines) if line.strip()), 0)
    if lines[first].lstrip().startswith("<"):
        # The SPA's index.html served at /llms.txt: the route was never added
        # and the catch-all answered instead.
        return [
            Finding(
                ERROR,
                "E_HTML",
                first + 1,
                "this is HTML, not Markdown - /llms.txt is probably falling through to the app",
            )
        ]

    state = _Scan()
    for number, line in enumerate(lines, start=1):
        if state.pending_description and state.pending_description != number:
            state.continued = bool(CONTINUATION.match(line))
            _settle_description(state, findings)
        heading = HEADING.match(line)
        if heading:
            _heading(state, findings, number, heading)
            continue
        if line.strip().startswith(">") and state.h1_line and not state.summary_line:
            if not state.body_seen:
                state.summary_line = number
            continue
        if BULLET.match(line):
            _bullet(state, findings, number, line)
            continue
        if CONTINUATION.match(line):
            # Wrapping a description over two lines is ordinary Markdown, and
            # flagging it as a missing description is the validator's fault.
            state.continued = True
            if state.section:
                state.section_prose = True
            continue
        if line.strip():
            state.body_seen = True
            if state.section:
                state.section_prose = True

    _settle_description(state, findings)
    findings.extend(_whole_file(state))
    return sorted(findings, key=lambda f: (f.line, f.code))


@dataclass
class _Scan:
    h1_line: int = 0
    h1_text: str = ""
    summary_line: int = 0
    body_seen: bool = False
    section: str = ""
    section_line: int = 0
    section_links: int = 0
    sections: list[tuple[str, int]] = field(default_factory=list)
    optional_line: int = 0
    last_section_line: int = 0
    section_prose: bool = False
    plain_bullets: list[int] = field(default_factory=list)
    continued: bool = False
    pending_description: int = 0
    urls: dict[str, int] = field(default_factory=dict)


def _heading(state: _Scan, findings: list[Finding], number: int, match: re.Match[str]) -> None:
    level = len(match.group("hashes"))
    title = match.group("text").strip()
    if level == 1:
        if state.h1_line:
            findings.append(
                Finding(ERROR, "E_MULTIPLE_H1", number, "a second H1; the file names one thing")
            )
            return
        if state.body_seen:
            findings.append(
                Finding(ERROR, "E_H1_NOT_FIRST", number, "content appears before the H1 title")
            )
        state.h1_line, state.h1_text = number, title
        if not title:
            findings.append(
                Finding(WARNING, "W_EMPTY_TITLE", number, "the H1 has no name in it")
            )
        return
    if level == 2:
        _close_section(state, findings)
        state.section, state.section_line, state.section_links = title, number, 0
        state.section_prose = False
        state.plain_bullets = []
        state.sections.append((title.lower(), number))
        state.last_section_line = number
        if title.lower() == OPTIONAL:
            state.optional_line = number
        return
    findings.append(
        Finding(
            WARNING,
            "W_DEEP_HEADING",
            number,
            f"H{level} is outside the format; a reader flattens it into the section above",
        )
    )


def _bullet(state: _Scan, findings: list[Finding], number: int, line: str) -> None:
    match = LINK.match(line)
    if match is None:
        # Judged when the section ends: one bad entry among links is a mistake,
        # a section of bulleted prose is a style, and real files use both.
        if state.section:
            state.plain_bullets.append(number)
            # Text, of a sort: the section is not empty, it is just not a map.
            state.section_prose = True
        return
    state.section_links += 1
    url = (match.group("url") or "").strip()
    if not url:
        findings.append(Finding(ERROR, "E_EMPTY_URL", number, "the link has no URL"))
        return
    if not url.startswith(("http://", "https://")):
        findings.append(
            Finding(
                WARNING,
                "W_RELATIVE_URL",
                number,
                f"{url!r} is relative; this file is read on its own, "
                "with no page to resolve it against",
            )
        )
    if url in state.urls:
        findings.append(
            Finding(
                WARNING,
                "W_DUPLICATE_URL",
                number,
                f"{url} is already listed on line {state.urls[url]}",
            )
        )
    else:
        state.urls[url] = number
    if not (match.group("desc") or "").strip():
        # Decided at the next line: a description may be wrapped onto it.
        state.pending_description = number


def _settle_description(state: _Scan, findings: list[Finding]) -> None:
    """Called once the following line is known."""
    if not state.pending_description:
        return
    if not state.continued:
        findings.append(
            Finding(
                WARNING,
                "W_NO_DESCRIPTION",
                state.pending_description,
                "no description: a model has only the label to judge whether to fetch this",
            )
        )
    state.pending_description = 0
    state.continued = False


def _close_section(state: _Scan, findings: list[Finding]) -> None:
    if state.plain_bullets:
        if state.section_links:
            findings.extend(
                Finding(
                    ERROR,
                    "E_BAD_LINK",
                    number,
                    "a bullet among links must be `- [label](url): description`",
                )
                for number in state.plain_bullets
            )
        else:
            findings.append(
                Finding(
                    WARNING,
                    "W_PROSE_BULLETS",
                    state.plain_bullets[0],
                    f"section {state.section!r} lists no links, "
                    "so a model gets nothing to fetch from it",
                )
            )
        state.plain_bullets = []
    if state.section and not state.section_links and not state.section_prose:
        findings.append(
            Finding(
                WARNING,
                "W_EMPTY_SECTION",
                state.section_line,
                f"section {state.section!r} has neither links nor text",
            )
        )


def _whole_file(state: _Scan) -> list[Finding]:
    findings: list[Finding] = []
    _close_section(state, findings)
    if not state.h1_line:
        findings.append(
            Finding(
                ERROR, "E_NO_H1", 0, "no H1: the file must open with the name of the site"
            )
        )
    if state.h1_line and not state.summary_line:
        findings.append(
            Finding(
                WARNING,
                "W_NO_SUMMARY",
                state.h1_line,
                "no `> summary` after the title; it is the one line every reader keeps",
            )
        )
    if not state.sections:
        findings.append(
            Finding(
                WARNING,
                "W_NO_SECTIONS",
                state.h1_line,
                "no `##` sections, so nothing is mapped",
            )
        )
    seen: dict[str, int] = {}
    for title, number in state.sections:
        if title in seen:
            findings.append(
                Finding(
                    WARNING,
                    "W_DUPLICATE_SECTION",
                    number,
                    f"a second section named {title!r}; the first is on line {seen[title]}",
                )
            )
        else:
            seen[title] = number
    if state.optional_line and state.optional_line != state.last_section_line:
        findings.append(
            Finding(
                WARNING,
                "W_OPTIONAL_NOT_LAST",
                state.optional_line,
                "`## Optional` says what may be skipped, so everything after it is skipped too",
            )
        )
    return findings


def is_valid(findings: list[Finding], *, strict: bool = False) -> bool:
    """Whether the file passes. Warnings only count when asked for."""
    levels = {f.level for f in findings}
    if ERROR in levels:
        return False
    return not (strict and WARNING in levels)
