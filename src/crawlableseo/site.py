"""One declaration of a site; every output is derived from it."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .llmstxt import LlmsSection, llms_txt
from .page import NotFound, Page
from .robots import DEFAULT_AI_CRAWLERS, robots_txt
from .shell import render_shell
from .sitemap import SitemapEntry, sitemap_xml
from .urls import page_url

Resolver = Callable[[str, dict[str, str]], "Page | NotFound | None"]
UrlSupplier = Callable[[], Iterable["DynamicUrl"]]


@dataclass(frozen=True)
class DynamicUrl:
    """One URL of a dynamic route, for the sitemap.

    ``params`` must be the same parameters the resolver puts on the page it
    returns, because both the canonical tag and this entry are built from
    them by :func:`page_url`.
    """

    path: str
    params: dict[str, str] | None = None
    lastmod: str | None = None
    changefreq: str = "weekly"
    priority: float = 0.5


@dataclass
class _Dynamic:
    prefix: str
    resolver: Resolver
    urls: UrlSupplier | None


class Site:
    """The site's crawlable surface.

    A static page is declared once with :meth:`page` and appears in the
    shell's tags and in the sitemap. A dynamic route is declared with
    :meth:`dynamic`: a resolver builds the page for a request, and an
    optional supplier lists that route's URLs for the sitemap.
    """

    def __init__(
        self,
        base_url: str,
        *,
        shell: str | Path | None = None,
        shell_html: str | None = None,
        name: str = "",
        twitter_site: str = "",
        default_og_image: str | None = None,
        mount_id: str = "root",
        default_title: str = "",
        default_description: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.twitter_site = twitter_site
        self.default_og_image = default_og_image
        self.mount_id = mount_id
        self.default_title = default_title or name
        self.default_description = default_description
        if (shell is None) == (shell_html is None):
            raise ValueError("pass exactly one of shell (a path) or shell_html (markup)")
        self._shell_path = Path(shell) if shell is not None else None
        self._shell_cache: str | None = shell_html
        self._pages: dict[str, Page] = {}
        self._dynamic: list[_Dynamic] = []
        self._noindex_prefixes: list[str] = []

    # -- declaration --------------------------------------------------

    def page(
        self,
        path: str,
        *,
        title: str,
        description: str,
        body: str = "",
        params: dict[str, str] | None = None,
        jsonld: tuple[dict[str, object], ...] = (),
        og_image: str | None = None,
        index: bool = True,
        follow: bool = True,
        in_sitemap: bool = True,
        changefreq: str = "weekly",
        priority: float = 0.5,
        lastmod: str | None = None,
    ) -> Page:
        """Declare a static page.

        The arguments are :class:`Page`'s fields, spelled out rather than
        forwarded as ``**kwargs``: this is the call people write most often,
        and it should complete and type-check in an editor.
        """
        page = Page(
            title=title,
            description=description,
            body=body,
            params=params or {},
            jsonld=jsonld,
            og_image=og_image,
            index=index,
            follow=follow,
            in_sitemap=in_sitemap,
            changefreq=changefreq,
            priority=priority,
            lastmod=lastmod,
        )
        self._pages[_normalise(path)] = page
        return page

    def add(self, path: str, page: Page) -> Page:
        """Declare a static page from a :class:`Page` you built yourself."""
        self._pages[_normalise(path)] = page
        return page

    def dynamic(
        self, prefix: str, *, urls: UrlSupplier | None = None
    ) -> Callable[[Resolver], Resolver]:
        """Register a resolver for every path under ``prefix``.

        The resolver returns a :class:`Page`, or :class:`NotFound` for a URL
        that has no content. Returning None falls through to the next
        resolver, then to the site defaults.
        """

        def decorate(resolver: Resolver) -> Resolver:
            self._dynamic.append(_Dynamic(_normalise(prefix), resolver, urls))
            return resolver

        return decorate

    def noindex(self, *prefixes: str) -> None:
        """Mark private or utility route prefixes as never indexable."""
        self._noindex_prefixes.extend(_normalise(p) for p in prefixes)

    # -- resolution ---------------------------------------------------

    def resolve(self, path: str, query: dict[str, str] | None = None) -> Page:
        path = _normalise(path)
        query = query or {}

        for prefix in self._noindex_prefixes:
            if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                return self._hidden()

        declared = self._pages.get(path)
        if declared is not None:
            return declared

        for entry in self._dynamic:
            if path == entry.prefix or path.startswith(entry.prefix.rstrip("/") + "/"):
                result = entry.resolver(path, query)
                if isinstance(result, NotFound):
                    return self._hidden(status=404)
                if result is not None:
                    return result

        # An unknown path is not a second copy of the home page. Answering
        # 200 there turns every typo and every stale link into an indexable
        # duplicate of the site's most important page.
        return self._hidden(status=404)

    def _hidden(self, status: int = 200) -> Page:
        """The site's fallback card for a page no crawler should index."""
        return Page(
            title=self.default_title,
            description=self.default_description,
            index=False,
            follow=False,
            in_sitemap=False,
            status=status,
        )

    def canonical(self, path: str, page: Page) -> str:
        return page_url(self.base_url, path, page.params)

    # -- outputs ------------------------------------------------------

    def shell(self) -> str:
        """The built shell, read once and kept in memory.

        Call :meth:`reload_shell` after a new frontend build, or restart the
        process: a long-lived server otherwise serves the previous bundle's
        script tags for as long as it runs.
        """
        if self._shell_cache is None:
            assert self._shell_path is not None
            self._shell_cache = self._shell_path.read_text(encoding="utf-8")
        return self._shell_cache

    def reload_shell(self) -> None:
        if self._shell_path is not None:
            self._shell_cache = None

    def render(self, path: str, query: dict[str, str] | None = None) -> tuple[str, int]:
        """Return ``(html, status)`` for a request path."""
        page = self.resolve(path, query)
        html = render_shell(
            self.shell(),
            page,
            canonical=self.canonical(_normalise(path), page),
            base_url=self.base_url,
            site_name=self.name,
            twitter_site=self.twitter_site,
            default_og_image=self.default_og_image,
            mount_id=self.mount_id,
        )
        return html, page.status

    def routes(self) -> list[tuple[str, dict[str, str]]]:
        """Every URL this site can name: static pages, then each dynamic
        route's own list. What a prerender writes, and what a crawl would find."""
        found: list[tuple[str, dict[str, str]]] = [
            (path, dict(page.params)) for path, page in sorted(self._pages.items())
        ]
        for entry in self._dynamic:
            for url in entry.urls() if entry.urls else ():
                found.append((_normalise(url.path), dict(url.params or {})))
        return found

    def sitemap_entries(self) -> list[SitemapEntry]:
        entries = [
            SitemapEntry(
                loc=page_url(self.base_url, path, page.params),
                lastmod=page.lastmod,
                changefreq=page.changefreq,
                priority=page.priority,
            )
            for path, page in sorted(self._pages.items())
            if page.in_sitemap and page.index
        ]
        for entry in self._dynamic:
            for url in entry.urls() if entry.urls else ():
                entries.append(
                    SitemapEntry(
                        loc=page_url(self.base_url, url.path, url.params),
                        lastmod=url.lastmod,
                        changefreq=url.changefreq,
                        priority=url.priority,
                    )
                )
        return entries

    def sitemap(self) -> str:
        return sitemap_xml(self.sitemap_entries())

    def robots(
        self,
        *,
        disallow: Sequence[str] = (),
        ai_crawlers: Sequence[str] | None = DEFAULT_AI_CRAWLERS,
        extra_lines: Sequence[str] = (),
    ) -> str:
        return robots_txt(
            self.base_url,
            disallow=list(disallow) + self._noindex_prefixes,
            ai_crawlers=ai_crawlers,
            extra_lines=extra_lines,
        )

    def llms(
        self, summary: str, sections: Iterable[LlmsSection], *, notes: Sequence[str] = ()
    ) -> str:
        return llms_txt(self.name, summary, sections, notes=notes)


def _normalise(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"
