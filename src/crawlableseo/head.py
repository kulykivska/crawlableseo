"""The block of tags written into <head> for one page."""

from __future__ import annotations

import html
import json

from .page import Page
from .shell_marker import MARKER


def head_block(
    page: Page,
    *,
    canonical: str,
    base_url: str,
    site_name: str = "",
    twitter_site: str = "",
    default_og_image: str | None = None,
) -> str:
    e = html.escape
    img = page.og_image or default_og_image
    if img and img.startswith("/"):
        img = base_url.rstrip("/") + img

    lines = [
        MARKER,
        f'<link rel="canonical" href="{e(canonical)}" />',
        f'<meta name="robots" content="{page.robots_value()}" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:title" content="{e(page.title)}" />',
        f'<meta property="og:description" content="{e(page.description)}" />',
        f'<meta property="og:url" content="{e(canonical)}" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:title" content="{e(page.title)}" />',
        f'<meta name="twitter:description" content="{e(page.description)}" />',
    ]
    if site_name:
        lines.insert(4, f'<meta property="og:site_name" content="{e(site_name)}" />')
    if twitter_site:
        lines.append(f'<meta name="twitter:site" content="{e(twitter_site)}" />')
    if img:
        lines += [
            f'<meta property="og:image" content="{e(img)}" />',
            '<meta property="og:image:width" content="1200" />',
            '<meta property="og:image:height" content="630" />',
            f'<meta name="twitter:image" content="{e(img)}" />',
        ]
    lines += [_jsonld_tag(obj) for obj in page.jsonld]
    return "\n".join(lines)


def _jsonld_tag(obj: dict[str, object]) -> str:
    # A "</" anywhere in the data would close the script element early, so the
    # rest of the document becomes the browser's problem. Escaping the slash
    # is valid JSON and parses back to the same string.
    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return '<script type="application/ld+json">' + payload + "</script>"
