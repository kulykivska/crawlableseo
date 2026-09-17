"""The one description of a page, shared by every output the library makes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# Bing's site scanner reports a description outside this range as an SEO
# error, and Google truncates at roughly the same point.
MIN_DESCRIPTION = 50
MAX_DESCRIPTION = 160
# Google renders about this much of a title before the ellipsis.
MAX_TITLE = 60


@dataclass(frozen=True)
class Page:
    """Everything the shell, the sitemap and llms.txt need about one URL.

    ``body`` is crawlable HTML placed inside the mount node. The framework
    replaces the node's children when it mounts, so users never see it; a
    crawler that does not run JavaScript reads it as the page's content.
    """

    title: str
    description: str
    body: str = ""
    # Extra query parameters that belong in the canonical URL. A parameter
    # that changes the content belongs here; a tracking parameter does not.
    params: dict[str, str] = field(default_factory=dict)
    jsonld: tuple[dict[str, object], ...] = ()
    og_image: str | None = None
    index: bool = True
    # Kept separate from ``index``: a page can be worth excluding from the
    # index while its outgoing links are still worth crawling.
    follow: bool = True
    status: int = 200
    # Sitemap hints. ``in_sitemap=False`` keeps a real page out of it.
    in_sitemap: bool = True
    changefreq: str = "weekly"
    priority: float = 0.5
    lastmod: str | None = None

    def robots_value(self) -> str:
        if self.index:
            return "index, follow" if self.follow else "index, nofollow"
        return "noindex, follow" if self.follow else "noindex, nofollow"

    def clipped(self) -> Page:
        """Title and description cut to the lengths search engines keep.

        Applied once, where the tags are written, rather than trusted to
        every caller: pages built from database strings have no length limit
        of their own.
        """
        return replace(
            self,
            title=_clip(self.title, MAX_TITLE),
            description=_clip(self.description, MAX_DESCRIPTION),
        )


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + "…"


@dataclass(frozen=True)
class NotFound:
    """Returned by a resolver for a URL that looks valid but has no content.

    Answering 200 with an "isn't available" screen is what search engines
    file as a soft 404: the page is counted, judged empty, and the crawl
    budget spent on it is gone. Say 404 instead.
    """

    canonical_to: str = "/"
