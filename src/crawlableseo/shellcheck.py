"""Read a built shell and say what will go wrong when it is filled.

Every check here comes from the way `render_shell` works: what it needs to
find, what it will not touch, and what it will end up duplicating. A shell that
fails these still serves a browser perfectly, which is why nobody notices.
"""

from __future__ import annotations

import re

from .findings import ERROR, WARNING, Finding, line_of
from .shell_marker import MARKER

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEAD_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title\b[^>]*>(?P<text>.*?)</title>", re.IGNORECASE | re.DOTALL)
_DESC_RE = re.compile(r"""<meta\s+name=["']description["'][^>]*>""", re.IGNORECASE)
_CANONICAL_RE = re.compile(r"""<link\s[^>]*rel=["']canonical["'][^>]*>""", re.IGNORECASE)
_ROBOTS_RE = re.compile(r"""<meta\s+name=["']robots["'][^>]*>""", re.IGNORECASE)
_OG_RE = re.compile(r"""<meta\s+property=["']og:[^"']+["'][^>]*>""", re.IGNORECASE)
_BASE_RE = re.compile(r"<base\b[^>]*>", re.IGNORECASE)
_CHARSET_RE = re.compile(r"<meta\s+charset=", re.IGNORECASE)
_VIEWPORT_RE = re.compile(r"""<meta\s+name=["']viewport["']""", re.IGNORECASE)

# What render_shell fills: an empty mount node and nothing else.
EMPTY_MOUNT = r"(<div\b[^>]*\bid=[\"']?{id}[\"']?[^>]*>)\s*</div>"
ANY_MOUNT = r"<div\b[^>]*\bid=[\"']?{id}[\"']?[^>]*>"


def _outside_comments(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    spans = [m.span() for m in _COMMENT_RE.finditer(text)]
    pos = 0
    while pos <= len(text):
        match = pattern.search(text, pos)
        if match is None:
            return None
        inside = next((b for a, b in spans if a <= match.start() < b), None)
        if inside is None:
            return match
        pos = inside
    return None


def check_shell(html: str, *, mount_id: str = "root") -> list[Finding]:
    """Every problem in the shell, in the order they appear."""
    findings: list[Finding] = []
    if not html.strip():
        return [Finding(ERROR, "E_EMPTY", 0, "the shell is empty")]

    if MARKER in html:
        # render_shell returns an already-marked template untouched, so every
        # page would be served with whatever tags this file already carries.
        findings.append(
            Finding(
                ERROR,
                "E_ALREADY_RENDERED",
                line_of(html, html.index(MARKER)),
                f"this shell already contains {MARKER}; rendering it is a no-op "
                "and every URL would serve these same tags",
            )
        )

    head = _outside_comments(_HEAD_RE, html)
    if head is None:
        findings.append(
            Finding(
                ERROR,
                "E_NO_HEAD",
                0,
                "no <head>: the tags have nowhere to go and end up after </html>",
            )
        )

    findings.extend(_mount(html, mount_id))
    findings.extend(_title(html))

    if _outside_comments(_DESC_RE, html) is None:
        findings.append(
            Finding(
                WARNING,
                "W_NO_DESCRIPTION_TAG",
                0,
                "no <meta name=description>: one is inserted, but a build that "
                "ships without it has nothing for a crawler that reads the file as built",
            )
        )
    findings.extend(_duplicates(html))

    if (base := _outside_comments(_BASE_RE, html)) is not None:
        findings.append(
            Finding(
                WARNING,
                "W_BASE_TAG",
                line_of(html, base.start()),
                "<base> changes what every relative URL in the injected block resolves to",
            )
        )
    for pattern, code, what in (
        (_CHARSET_RE, "W_NO_CHARSET", "<meta charset>"),
        (_VIEWPORT_RE, "W_NO_VIEWPORT", "<meta name=viewport>"),
    ):
        if _outside_comments(pattern, html) is None:
            findings.append(Finding(WARNING, code, 0, f"no {what} in the shell"))
    return sorted(findings, key=lambda f: (f.line, f.code))


def _mount(html: str, mount_id: str) -> list[Finding]:
    empty = re.compile(EMPTY_MOUNT.format(id=re.escape(mount_id)), re.IGNORECASE)
    any_node = re.compile(ANY_MOUNT.format(id=re.escape(mount_id)), re.IGNORECASE)
    if _outside_comments(empty, html) is not None:
        return []
    found = _outside_comments(any_node, html)
    if found is None:
        return [
            Finding(
                ERROR,
                "E_NO_MOUNT",
                0,
                f"no <div id=\"{mount_id}\">: the crawlable body has nowhere to go, "
                "so pages render with tags and no content",
            )
        ]
    return [
        # The regex that fills the node requires it to be empty, so a node with
        # anything in it is skipped - silently, and the page looks fine.
        Finding(
            ERROR,
            "E_MOUNT_NOT_EMPTY",
            line_of(html, found.start()),
            f"<div id=\"{mount_id}\"> is not empty; the crawlable body is only "
            "written into an empty mount node",
        )
    ]


def _title(html: str) -> list[Finding]:
    real = _outside_comments(_TITLE_RE, html)
    if real is not None:
        return []
    commented = _TITLE_RE.search(html)
    if commented is not None:
        return [
            Finding(
                WARNING,
                "W_TITLE_ONLY_IN_COMMENT",
                line_of(html, commented.start()),
                "the only <title> here is inside a comment; a title is inserted "
                "instead, and a naive renderer would have eaten the comment",
            )
        ]
    return [
        Finding(
            WARNING,
            "W_NO_TITLE",
            0,
            "no <title>: one is inserted per URL, but the file as built has none",
        )
    ]


def _duplicates(html: str) -> list[Finding]:
    out: list[Finding] = []
    for pattern, code, what in (
        (_CANONICAL_RE, "W_SHELL_CANONICAL", "a canonical link"),
        (_ROBOTS_RE, "W_SHELL_ROBOTS", "a robots meta tag"),
        (_OG_RE, "W_SHELL_OG", "Open Graph tags"),
    ):
        match = _outside_comments(pattern, html)
        if match is not None:
            out.append(
                Finding(
                    WARNING,
                    code,
                    line_of(html, match.start()),
                    f"the shell already carries {what}; the injected block adds its "
                    "own, and a document with two is a document a crawler has to guess at",
                )
            )
    return out
