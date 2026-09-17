"""robots.txt, with the two rules that cost the most to learn."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# Crawlers that feed AI answers. Being quotable by them is a distribution
# channel, and the crawlable body this library injects is written for them.
DEFAULT_AI_CRAWLERS: tuple[str, ...] = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "PerplexityBot",
    "ClaudeBot",
    "Claude-SearchBot",
    "Google-Extended",
)


def robots_txt(
    base_url: str,
    *,
    disallow: Sequence[str] = (),
    allow: Sequence[str] = ("/",),
    sitemap: str | Iterable[str] | None = "/sitemap.xml",
    ai_crawlers: Sequence[str] | None = DEFAULT_AI_CRAWLERS,
    extra_lines: Sequence[str] = (),
) -> str:
    """Build robots.txt.

    Two warnings, both of them expensive in practice:

    Do not disallow the JSON your own app fetches. A modern crawler renders
    the page like a browser; blocking the API it calls leaves every route
    empty at render time, and empty routes are filed as soft 404s. Disallow
    the write and admin surfaces, not the read-only data.

    There is no Content-Signal line and no option to add one. Lighthouse's
    robots.txt validator does not know the directive, reports it as an
    unknown directive and takes points off the SEO score of every page on
    the site. Absence already means "no restriction".
    """
    base_url = base_url.rstrip("/")
    lines: list[str] = ["User-agent: *"]
    lines += [f"Allow: {p}" for p in allow]
    lines += [f"Disallow: {p}" for p in disallow]

    for agent in ai_crawlers or ():
        lines += ["", f"User-agent: {agent}", "Allow: /"]

    lines += list(extra_lines)

    if sitemap:
        maps = [sitemap] if isinstance(sitemap, str) else list(sitemap)
        lines.append("")
        for m in maps:
            lines.append(f"Sitemap: {m if m.startswith('http') else base_url + m}")

    lines.append("")
    return "\n".join(lines)
