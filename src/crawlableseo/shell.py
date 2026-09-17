"""Inject per-URL metadata and crawlable content into a built SPA shell."""

from __future__ import annotations

import html
import re

from .head import head_block
from .page import Page
from .shell_marker import MARKER

__all__ = ["MARKER", "render_shell"]

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_TITLE_RE = re.compile(r"<title\b[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
_DESC_RE = re.compile(
    r"""<meta\s+name=["']description["'][^>]*>""", re.IGNORECASE
)


def _comment_spans(template: str) -> list[tuple[int, int]]:
    return [m.span() for m in _COMMENT_RE.finditer(template)]


def _search_outside_comments(
    pattern: re.Pattern[str], template: str, spans: list[tuple[int, int]]
) -> re.Match[str] | None:
    """First match that is not inside an HTML comment.

    A build-time comment that merely mentions ``<title>`` is not the title.
    Matching it and replacing it destroys the comment's closing marker, which
    comments out the rest of the head: the stylesheet and the bundle script
    become comment text, and the site serves a blank page with no console
    error and no failed request.
    """
    pos = 0
    while pos <= len(template):
        m = pattern.search(template, pos)
        if m is None:
            return None
        inside = next((b for a, b in spans if a <= m.start() < b), None)
        if inside is None:
            return m
        # Resume after the comment, not after the match: this match started
        # inside the comment and swallowed the real tag that follows it.
        pos = inside
    return None


def render_shell(
    template: str,
    page: Page,
    *,
    canonical: str,
    base_url: str,
    site_name: str = "",
    twitter_site: str = "",
    default_og_image: str | None = None,
    mount_id: str = "root",
) -> str:
    """Return the shell with this page's tags and crawlable body in place."""
    if MARKER in template:
        return template

    page = page.clipped()
    e = html.escape

    # Both tags are located in one pass over the original document, then the
    # edits are applied back to front so the earlier offsets stay valid.
    # Slicing, never re.sub with a replacement string: a title built from a
    # query parameter can contain a backslash escape, which re would read as
    # a group reference and raise on, turning an ordinary URL into a 500.
    spans = _comment_spans(template)
    title_tag = f"<title>{e(page.title)}</title>"
    desc_tag = f'<meta name="description" content="{e(page.description)}" />'
    edits: list[tuple[int, int, str]] = []
    missing: list[str] = []

    for pattern, tag in ((_TITLE_RE, title_tag), (_DESC_RE, desc_tag)):
        m = _search_outside_comments(pattern, template, spans)
        if m:
            edits.append((m.start(), m.end(), tag))
        else:
            missing.append(tag)

    out = template
    for start, end, tag in sorted(edits, reverse=True):
        out = out[:start] + tag + out[end:]
    for tag in missing:
        out = _insert_into_head(out, tag)

    out = _insert_into_head(
        out,
        head_block(
            page,
            canonical=canonical,
            base_url=base_url,
            site_name=site_name,
            twitter_site=twitter_site,
            default_og_image=default_og_image,
        ),
    )

    if page.body:
        out = _fill_mount_node(out, mount_id, page.body)
    return out


def _insert_into_head(template: str, block: str) -> str:
    idx = template.lower().find("</head>")
    if idx == -1:
        return template + "\n" + block
    return template[:idx] + block + "\n" + template[idx:]


_MOUNT_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _mount_re(mount_id: str) -> re.Pattern[str]:
    cached = _MOUNT_RE_CACHE.get(mount_id)
    if cached is None:
        cached = re.compile(
            r"(<div\b[^>]*\bid=[\"']?" + re.escape(mount_id) + r"[\"']?[^>]*>)\s*</div>",
            re.IGNORECASE,
        )
        _MOUNT_RE_CACHE[mount_id] = cached
    return cached


def _fill_mount_node(template: str, mount_id: str, body: str) -> str:
    m = _mount_re(mount_id).search(template)
    if not m:
        return template
    return template[: m.start()] + m.group(1) + body + "</div>" + template[m.end() :]
