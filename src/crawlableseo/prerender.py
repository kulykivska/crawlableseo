"""Write the whole site out as files, for a host that runs no code.

The library's usual home is a server that fills the shell per request. A static
build has no server, which is the case that most needs this: the same
declaration becomes one file per route, plus robots.txt and sitemap.xml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .site import Site


@dataclass
class PrerenderResult:
    written: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def describe(self) -> str:
        lines = [f"{len(self.written)} file(s) written"]
        for path, why in self.skipped:
            lines.append(f"skipped {path}: {why}")
        return "\n".join(lines)


def file_for(out: Path, path: str) -> Path:
    """`/` becomes index.html, `/pricing` becomes pricing/index.html.

    The directory form, because that is what every static host serves at
    `/pricing` without a redirect and without `.html` in the address bar.
    """
    clean = path.strip("/")
    return out / "index.html" if not clean else out / clean / "index.html"


def prerender(
    site: Site, out: Path, *, robots: bool = True, sitemap: bool = True
) -> PrerenderResult:
    result = PrerenderResult()
    out.mkdir(parents=True, exist_ok=True)

    for path, params in site.routes():
        if params:
            # A static host cannot answer /product?id=7 with its own file.
            # Saying so is better than writing a file nothing will ever serve.
            result.skipped.append(
                (path, "has query parameters; a static host cannot route them")
            )
            continue
        html, status = site.render(path)
        if status != 200:
            result.skipped.append((path, f"resolves to {status}"))
            continue
        target = file_for(out, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        result.written.append(str(target.relative_to(out)))

    if robots:
        (out / "robots.txt").write_text(site.robots(), encoding="utf-8")
        result.written.append("robots.txt")
    if sitemap:
        (out / "sitemap.xml").write_text(site.sitemap(), encoding="utf-8")
        result.written.append("sitemap.xml")
    return result
