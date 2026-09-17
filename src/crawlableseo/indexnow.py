"""IndexNow: tell search engines a URL changed, instead of waiting to be crawled.

The protocol is small. The site publishes a key at ``/<key>.txt`` whose body
is the key itself, then POSTs changed URLs with that key. Bing, Yandex,
Seznam and Naver share one endpoint; Bing matters most because it feeds
ChatGPT search and Copilot.

The key is public by design - anyone can read the key file - and grants
nothing beyond submitting URLs for that one host.

IndexNow is an accelerator, never a dependency: engines re-crawl on their own
schedule regardless, so a failed submission is logged and dropped, never
raised into the caller's request.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

logger = logging.getLogger("crawlableseo.indexnow")

ENDPOINT = "https://api.indexnow.org/indexnow"
# The protocol caps one submission at 10,000 URLs. Batching well below that
# keeps a whole-sitemap resubmit to a handful of requests.
BATCH = 500
_KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")


class IndexNow:
    """Client for one host.

    ``httpx`` is an optional dependency; install ``crawlableseo[indexnow]``
    to use this class.
    """

    def __init__(self, base_url: str, key: str | None, *, endpoint: str = ENDPOINT) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.key = self._validated(key)

    @staticmethod
    def _validated(key: str | None) -> str | None:
        k = (key or "").strip()
        if not k:
            return None
        if not _KEY_RE.match(k):
            logger.warning(
                "indexnow: key must be 8-128 characters of [A-Za-z0-9-]; disabled"
            )
            return None
        return k

    @property
    def enabled(self) -> bool:
        return self.key is not None

    @property
    def key_path(self) -> str | None:
        """Path the key file must be served at, e.g. ``/abc123.txt``."""
        return f"/{self.key}.txt" if self.key else None

    def absolute(self, urls: Sequence[str]) -> list[str]:
        out = []
        for u in urls:
            if not u:
                continue
            out.append(u if u.startswith("http") else self.base_url + u)
        return out

    async def submit(self, urls: Sequence[str]) -> bool:
        """POST the URLs. Returns False when disabled or when the call failed."""
        if not self.key:
            logger.debug("indexnow: no key configured, skipping %d url(s)", len(urls))
            return False
        try:
            import httpx
        except ImportError:  # pragma: no cover - exercised by the extras test
            logger.warning("indexnow: httpx is not installed; install crawlableseo[indexnow]")
            return False

        host = self.base_url.split("://", 1)[-1].split("/", 1)[0]
        absolute = self.absolute(urls)
        ok = True
        async with httpx.AsyncClient(timeout=10.0) as client:
            for start in range(0, len(absolute), BATCH):
                chunk = absolute[start : start + BATCH]
                payload = {
                    "host": host,
                    "key": self.key,
                    "keyLocation": f"{self.base_url}{self.key_path}",
                    "urlList": chunk,
                }
                try:
                    response = await client.post(self.endpoint, json=payload)
                except Exception as exc:
                    logger.warning("indexnow: submission failed (%s)", exc)
                    ok = False
                    continue
                if response.status_code >= 400:
                    logger.warning(
                        "indexnow: %s rejected %d url(s): %s",
                        response.status_code,
                        len(chunk),
                        response.text[:200],
                    )
                    ok = False
                else:
                    logger.info("indexnow: submitted %d url(s)", len(chunk))
        return ok
