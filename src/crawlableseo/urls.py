"""The single place a page's URL is built.

Every URL this library emits - the canonical tag, the sitemap entry, the
IndexNow submission, the llms.txt link - comes from :func:`page_url`. When a
canonical and its sitemap entry are built by two different pieces of code
they drift, usually over one query parameter, and a search engine treats the
two spellings as two pages with identical content.
"""

from __future__ import annotations

from urllib.parse import quote


def page_url(base_url: str, path: str, params: dict[str, str] | None = None) -> str:
    base_url = base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    if path != "/":
        path = path.rstrip("/") or "/"
    url = base_url + quote(path, safe="/-._~")
    if params:
        query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(params.items())
        )
        url = f"{url}?{query}"
    return url


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
