"""sitemap.xml, built from the same URL function as the canonical tag."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .urls import xml_escape

# The protocol's own ceiling. Past it a sitemap must be split and listed in
# an index; this library raises rather than shipping a file crawlers reject.
MAX_URLS = 50_000


@dataclass(frozen=True)
class SitemapEntry:
    loc: str
    lastmod: str | None = None
    changefreq: str = "weekly"
    priority: float = 0.5


def sitemap_xml(entries: Iterable[SitemapEntry]) -> str:
    entries = list(entries)
    if len(entries) > MAX_URLS:
        raise ValueError(
            f"a sitemap holds at most {MAX_URLS} URLs, got {len(entries)}; "
            "split it and publish a sitemap index"
        )
    body = "\n".join(_url_tag(e) for e in entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _url_tag(entry: SitemapEntry) -> str:
    parts = [f"  <url><loc>{xml_escape(entry.loc)}</loc>"]
    if entry.lastmod:
        parts.append(f"<lastmod>{xml_escape(entry.lastmod)}</lastmod>")
    parts.append(f"<changefreq>{entry.changefreq}</changefreq>")
    parts.append(f"<priority>{entry.priority:.1f}</priority></url>")
    return "".join(parts)
