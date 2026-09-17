"""One declaration, several outputs - and they must agree."""

from __future__ import annotations

import re

from crawlableseo import DynamicUrl, NotFound, Page, Site

SHELL = (
    "<!doctype html><html><head><title>t</title>"
    '<meta name="description" content="d" /></head>'
    '<body><div id="root"></div></body></html>'
)


def build_site() -> Site:
    site = Site(
        "https://example.com/",
        shell_html=SHELL,
        name="Example",
        default_title="Example",
        default_description="An example site.",
    )
    site.page(
        "/pricing",
        title="Pricing | Example",
        description="What it costs.",
        priority=0.5,
        body="<h1>Pricing</h1>",
    )
    site.noindex("/admin", "/login")

    @site.dynamic(
        "/race",
        urls=lambda: [
            DynamicUrl("/race", {"code": "ITA", "season": "2026"}, lastmod="2026-09-06")
        ],
    )
    def race(path: str, query: dict[str, str]) -> Page | NotFound | None:
        if query.get("code") == "GONE":
            return NotFound()
        return Page(
            title=f"{query.get('code', '?')} | Example",
            description="A race.",
            params={k: v for k, v in query.items() if k in ("code", "season")},
            body="<h1>Race</h1>",
        )

    return site


def canonical_of(html: str) -> str:
    return re.search(r'rel="canonical" href="([^"]+)"', html).group(1)  # type: ignore[union-attr]


def test_canonical_and_sitemap_cannot_drift():
    """The whole reason the library owns both.

    When the canonical tag and the sitemap entry are built separately they
    disagree over a parameter sooner or later, and the two spellings become
    two pages with identical content.
    """
    site = build_site()
    html, _ = site.render("/race", {"code": "ITA", "season": "2026"})
    assert canonical_of(html) in site.sitemap()


def test_tracking_parameters_stay_out_of_the_canonical():
    site = build_site()
    html, _ = site.render("/race", {"code": "ITA", "season": "2026", "utm_source": "x"})
    assert "utm_source" not in canonical_of(html)


def test_a_declared_page_appears_once_in_the_sitemap():
    xml = build_site().sitemap()
    assert xml.count("<loc>https://example.com/pricing</loc>") == 1


def test_unknown_paths_answer_404_not_a_copy_of_the_home_page():
    """A 200 here turns every typo and stale link into an indexable
    duplicate of the site's most important page."""
    html, status = build_site().render("/no-such-page")
    assert status == 404
    assert 'content="noindex, nofollow"' in html


def test_a_resolver_can_say_the_url_has_no_content():
    html, status = build_site().render("/race", {"code": "GONE"})
    assert status == 404
    assert 'content="noindex, nofollow"' in html


def test_private_prefixes_are_never_indexable_and_are_disallowed():
    site = build_site()
    html, _ = site.render("/admin/users")
    assert 'content="noindex, nofollow"' in html
    assert "Disallow: /admin" in site.robots()


def test_noindex_pages_stay_out_of_the_sitemap():
    site = build_site()
    site.page("/beta", title="Beta", description="Hidden.", index=False)
    assert "/beta" not in site.sitemap()


def test_trailing_slashes_resolve_to_one_url():
    site = build_site()
    a, _ = site.render("/pricing")
    b, _ = site.render("/pricing/")
    assert canonical_of(a) == canonical_of(b) == "https://example.com/pricing"
