"""robots.txt, sitemap.xml, llms.txt and IndexNow."""

from __future__ import annotations

import logging

import pytest

from crawlableseo import (
    IndexNow,
    LlmsSection,
    SitemapEntry,
    llms_txt,
    page_url,
    robots_txt,
    sitemap_xml,
)


def test_robots_lists_the_sitemap_and_allows_ai_crawlers():
    txt = robots_txt("https://example.com", disallow=["/admin"])
    assert "Sitemap: https://example.com/sitemap.xml" in txt
    assert "User-agent: GPTBot" in txt
    assert "Disallow: /admin" in txt


def test_robots_never_writes_content_signal():
    """Lighthouse's validator does not know the directive, reports it as
    unknown and takes points off the SEO score of every page."""
    txt = robots_txt(
        "https://example.com", extra_lines=["# a comment is fine"], ai_crawlers=None
    )
    assert "Content-Signal" not in txt
    assert "GPTBot" not in txt


def test_sitemap_escapes_ampersands():
    xml = sitemap_xml([SitemapEntry(page_url("https://e.com", "/race", {"a": "1", "b": "2"}))])
    assert "&amp;" in xml
    assert "?a=1&b=2" not in xml


def test_sitemap_refuses_to_exceed_the_protocol_limit():
    entries = [SitemapEntry(f"https://e.com/{i}") for i in range(50_001)]
    with pytest.raises(ValueError, match="sitemap index"):
        sitemap_xml(entries)


def test_page_url_is_stable_regardless_of_parameter_order():
    a = page_url("https://e.com", "/race", {"season": "2026", "code": "ITA"})
    b = page_url("https://e.com", "/race", {"code": "ITA", "season": "2026"})
    assert a == b


def test_llms_txt_has_the_expected_shape():
    out = llms_txt(
        "Example",
        "One paragraph about the site.",
        [LlmsSection("Docs", [("Guide", "https://e.com/guide", "How it works.")])],
    )
    assert out.startswith("# Example\n")
    assert "> One paragraph" in out
    assert "- [Guide](https://e.com/guide): How it works." in out


def test_indexnow_rejects_a_malformed_key(caplog):
    with caplog.at_level(logging.WARNING):
        client = IndexNow("https://e.com", "too short")
    assert not client.enabled
    assert client.key_path is None
    assert "8-128" in caplog.text


def test_indexnow_serves_the_key_at_its_own_path():
    client = IndexNow("https://e.com", "abcd1234efgh")
    assert client.key_path == "/abcd1234efgh.txt"


async def test_indexnow_without_a_key_is_a_no_op():
    client = IndexNow("https://e.com", None)
    assert await client.submit(["/a"]) is False


def test_indexnow_makes_paths_absolute():
    client = IndexNow("https://e.com", "abcd1234efgh")
    assert client.absolute(["/a", "https://e.com/b", ""]) == [
        "https://e.com/a",
        "https://e.com/b",
    ]
