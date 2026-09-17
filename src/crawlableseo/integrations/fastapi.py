"""Wire a :class:`~crawlableseo.site.Site` into FastAPI or Starlette.

``router(site)`` returns the crawler-facing endpoints plus the SPA catch-all.
Mount it last: the catch-all answers every path the rest of the app did not
claim.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

# Imported at module scope on purpose. FastAPI resolves a handler's
# annotations against its module's globals, so a Request imported inside the
# function is invisible to it: every request then fails validation with
# "query.request field required" instead of being served. This module is only
# imported by callers who already depend on FastAPI.
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..indexnow import IndexNow
from ..llmstxt import LlmsSection
from ..robots import DEFAULT_AI_CRAWLERS
from ..site import Site


def router(
    site: Site,
    *,
    disallow: Sequence[str] = (),
    ai_crawlers: Sequence[str] | None = DEFAULT_AI_CRAWLERS,
    llms: Callable[[], str] | None = None,
    indexnow: IndexNow | None = None,
    shell_cache_seconds: int = 0,
    text_cache_seconds: int = 3600,
    catch_all: bool = True,
) -> APIRouter:
    """Build an ``APIRouter`` serving robots.txt, sitemap.xml, llms.txt and the SPA."""
    api = APIRouter()
    text_headers = {"Cache-Control": f"public, max-age={text_cache_seconds}"}

    @api.get("/robots.txt", include_in_schema=False)
    async def robots() -> Response:
        return PlainTextResponse(
            site.robots(disallow=disallow, ai_crawlers=ai_crawlers), headers=text_headers
        )

    @api.get("/sitemap.xml", include_in_schema=False)
    async def sitemap() -> Response:
        return Response(
            site.sitemap(), media_type="application/xml", headers=text_headers
        )

    if llms is not None:
        @api.get("/llms.txt", include_in_schema=False)
        async def llms_route() -> Response:
            return PlainTextResponse(llms(), headers=text_headers)

    if indexnow is not None and indexnow.key_path:
        key = indexnow.key

        @api.get(indexnow.key_path, include_in_schema=False)
        async def indexnow_key() -> Response:
            # The body must be exactly the key: that is how the engine
            # verifies the submitter controls this host.
            return PlainTextResponse(
                key or "", headers={"Cache-Control": "public, max-age=86400"}
            )

    if catch_all:
        @api.get("/{path:path}", include_in_schema=False)
        async def spa(path: str, request: Request) -> Response:
            html, status = site.render("/" + path, dict(request.query_params))
            headers = (
                {"Cache-Control": f"public, max-age={shell_cache_seconds}"}
                if shell_cache_seconds
                else {"Cache-Control": "no-cache"}
            )
            return HTMLResponse(html, status_code=status, headers=headers)

    return api


__all__ = ["LlmsSection", "router"]
