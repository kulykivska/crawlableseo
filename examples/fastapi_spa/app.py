"""A runnable example: a tiny catalogue SPA made crawlable.

    pip install "crawlableseo[fastapi]" uvicorn
    uvicorn examples.fastapi_spa.app:app --reload

Then compare what a browser gets with what a crawler gets:

    curl -s localhost:8000/product?id=2 | grep -E "<title>|canonical"
    curl -s localhost:8000/sitemap.xml
    curl -s localhost:8000/robots.txt
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from crawlableseo import DynamicUrl, LlmsSection, NotFound, Page, Site
from crawlableseo.integrations.fastapi import router

BASE_URL = "http://localhost:8000"

# Whatever your build produces. Inlined here so the example runs with no
# frontend build step; a real app passes shell="frontend/dist/index.html".
SHELL = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Catalogue</title>
    <meta name="description" content="A catalogue." />
  </head>
  <body><div id="root"></div></body>
</html>
"""


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    summary: str


CATALOGUE = {
    "1": Product(
        "1", "Desk lamp", "A warm 2700K lamp with a weighted base and no visible cable."
    ),
    "2": Product(
        "2", "Wall clock", "A silent sweep movement in a birch case, 30 cm across."
    ),
}

site = Site(
    BASE_URL,
    shell_html=SHELL,
    name="Catalogue",
    default_title="Catalogue",
    default_description="Two products, described properly, and crawlable without JavaScript.",
)

site.page(
    "/",
    title="Catalogue",
    description="Two products, described properly, and crawlable without JavaScript.",
    body="<h1>Catalogue</h1><p>Everything we make, which is not much.</p>"
    '<ul><li><a href="/product?id=1">Desk lamp</a></li>'
    '<li><a href="/product?id=2">Wall clock</a></li></ul>',
    priority=1.0,
    changefreq="daily",
)

site.noindex("/admin")


@site.dynamic(
    "/product",
    urls=lambda: [
        DynamicUrl("/product", {"id": p.id}, priority=0.8) for p in CATALOGUE.values()
    ],
)
def product(path: str, query: dict[str, str]) -> Page | NotFound | None:
    item = CATALOGUE.get(query.get("id", ""))
    if item is None:
        # Not a 200 with an empty screen: that is what search engines file
        # as a soft 404, and the crawl budget spent on it is gone.
        return NotFound()
    return Page(
        title=f"{item.name} | Catalogue",
        description=item.summary,
        params={"id": item.id},
        body=f"<h1>{item.name}</h1><p>{item.summary}</p>"
        '<nav><a href="/">All products</a></nav>',
        jsonld=(
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": item.name,
                "description": item.summary,
                "url": f"{BASE_URL}/product?id={item.id}",
            },
        ),
        priority=0.8,
    )


app = FastAPI()


@app.get("/api/products")
def api_products() -> list[dict[str, str]]:
    return [{"id": p.id, "name": p.name} for p in CATALOGUE.values()]


# Mounted last: the catch-all answers every path the API did not claim.
app.include_router(
    router(
        site,
        disallow=["/api/admin"],
        llms=lambda: site.llms(
            "A two-product catalogue, used as the example app for crawlableseo.",
            [
                LlmsSection(
                    "Products",
                    [
                        (p.name, f"{BASE_URL}/product?id={p.id}", p.summary)
                        for p in CATALOGUE.values()
                    ],
                )
            ],
        ),
    )
)
