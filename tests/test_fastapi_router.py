"""The FastAPI router, end to end through a real client."""

from __future__ import annotations

import pytest

from crawlableseo import IndexNow, LlmsSection, NotFound, Page, Site
from crawlableseo.integrations.fastapi import router

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SHELL = (
    "<!doctype html><html><head><title>t</title>"
    '<meta name="description" content="d" /></head>'
    '<body><div id="root"></div></body></html>'
)


def build_app() -> FastAPI:
    site = Site(
        "https://example.com",
        shell_html=SHELL,
        name="Example",
        default_title="Example",
        default_description="An example site.",
    )
    site.page("/pricing", title="Pricing | Example", description="What it costs.")
    site.noindex("/admin")

    @site.dynamic("/product")
    def product(path: str, query: dict[str, str]) -> Page | NotFound | None:
        if query.get("id") != "1":
            return NotFound()
        return Page(title="Widget | Example", description="A widget.", params={"id": "1"})

    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(
        router(
            site,
            disallow=["/api/admin"],
            llms=lambda: site.llms(
                "An example site.",
                [LlmsSection("Pages", [("Pricing", "https://example.com/pricing", "Plans.")])],
            ),
            indexnow=IndexNow("https://example.com", "abcd1234efgh"),
        )
    )
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


def test_the_app_keeps_its_own_routes(client: TestClient):
    """The catch-all is mounted last and must not swallow the API."""
    assert client.get("/api/health").json() == {"ok": True}


def test_a_declared_page_is_served_from_the_shell(client: TestClient):
    r = client.get("/pricing")
    assert r.status_code == 200
    assert "<title>Pricing | Example</title>" in r.text
    assert 'rel="canonical" href="https://example.com/pricing"' in r.text


def test_crawler_files_are_served(client: TestClient):
    assert "Sitemap: https://example.com/sitemap.xml" in client.get("/robots.txt").text
    assert "Disallow: /api/admin" in client.get("/robots.txt").text
    assert "<urlset" in client.get("/sitemap.xml").text
    assert client.get("/llms.txt").text.startswith("# Example")


def test_the_indexnow_key_file_is_the_key_itself(client: TestClient):
    r = client.get("/abcd1234efgh.txt")
    assert r.status_code == 200
    assert r.text == "abcd1234efgh"


def test_a_url_with_no_content_answers_404(client: TestClient):
    r = client.get("/product", params={"id": "999"})
    assert r.status_code == 404
    assert 'content="noindex, nofollow"' in r.text
