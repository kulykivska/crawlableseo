"""Make a client-rendered SPA crawlable from its own HTML shell.

No headless browser, no SSR framework, no third-party rendering service:
the server fills in the shell's ``<head>`` and mount node per URL, and the
same declaration produces robots.txt, sitemap.xml and llms.txt.
"""

from __future__ import annotations

from .findings import Finding, is_valid
from .head import head_block
from .indexnow import IndexNow
from .llmscheck import check_llms_txt
from .llmstxt import LlmsSection, llms_txt
from .page import MAX_DESCRIPTION, MAX_TITLE, MIN_DESCRIPTION, NotFound, Page
from .prerender import PrerenderResult, prerender
from .robots import DEFAULT_AI_CRAWLERS, robots_txt
from .shell import MARKER, render_shell
from .shellcheck import check_shell
from .site import DynamicUrl, Site
from .sitemap import SitemapEntry, sitemap_xml
from .urls import page_url

__version__ = "0.3.1"

__all__ = [
    "DEFAULT_AI_CRAWLERS",
    "MARKER",
    "MAX_DESCRIPTION",
    "MAX_TITLE",
    "MIN_DESCRIPTION",
    "DynamicUrl",
    "Finding",
    "IndexNow",
    "LlmsSection",
    "NotFound",
    "Page",
    "PrerenderResult",
    "Site",
    "SitemapEntry",
    "__version__",
    "check_llms_txt",
    "check_shell",
    "head_block",
    "is_valid",
    "llms_txt",
    "page_url",
    "prerender",
    "render_shell",
    "robots_txt",
    "sitemap_xml",
]
