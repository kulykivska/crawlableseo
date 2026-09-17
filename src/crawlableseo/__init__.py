"""Make a client-rendered SPA crawlable from its own HTML shell.

No headless browser, no SSR framework, no third-party rendering service:
the server fills in the shell's ``<head>`` and mount node per URL, and the
same declaration produces robots.txt, sitemap.xml and llms.txt.
"""

from __future__ import annotations

from .head import head_block
from .indexnow import IndexNow
from .llmstxt import LlmsSection, llms_txt
from .page import MAX_DESCRIPTION, MAX_TITLE, MIN_DESCRIPTION, NotFound, Page
from .robots import DEFAULT_AI_CRAWLERS, robots_txt
from .shell import MARKER, render_shell
from .site import DynamicUrl, Site
from .sitemap import SitemapEntry, sitemap_xml
from .urls import page_url

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_AI_CRAWLERS",
    "MARKER",
    "MAX_DESCRIPTION",
    "MAX_TITLE",
    "MIN_DESCRIPTION",
    "DynamicUrl",
    "IndexNow",
    "LlmsSection",
    "NotFound",
    "Page",
    "Site",
    "SitemapEntry",
    "__version__",
    "head_block",
    "llms_txt",
    "page_url",
    "render_shell",
    "robots_txt",
    "sitemap_xml",
]
