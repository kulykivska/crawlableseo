# crawlableseo

Make a client-rendered single-page app crawlable from its own HTML shell.

No headless browser, no SSR framework, no third-party prerendering service. Your
Python server fills in the shell's `<head>` and mount node for each URL, and the
same declaration produces `robots.txt`, `sitemap.xml` and `llms.txt`.

```bash
pip install crawlableseo
```

## The problem

A Vite or CRA build ships one `index.html` with an empty `<div id="root">`. Every
URL on the site returns the same document: the same title, the same description,
no content. Google renders JavaScript and will often cope; Bing is slower to; and
the crawlers behind AI answers — GPTBot, PerplexityBot, ClaudeBot — mostly read
the HTML they are given. What they are given is an empty div.

The usual answers are to adopt a meta-framework, run a headless browser per
request, or pay a prerendering service. This library takes the fourth option:
serve the same static shell, but write the real title, description, canonical,
Open Graph, JSON-LD and a block of readable HTML into it before it goes out.

## Quickstart

```python
from fastapi import FastAPI
from crawlableseo import DynamicUrl, NotFound, Page, Site
from crawlableseo.integrations.fastapi import router

site = Site(
    "https://example.com",
    shell="frontend/dist/index.html",
    name="Example",
    default_title="Example",
    default_description="What this site is, in one sentence.",
)

site.page(
    "/pricing",
    title="Pricing | Example",
    description="Three plans, what each one includes, and what they cost.",
    body="<h1>Pricing</h1><p>Free, Pro and Team...</p>",
    priority=0.8,
)

site.noindex("/admin", "/login", "/settings")


@site.dynamic("/product", urls=lambda: [DynamicUrl("/product", {"id": p.id}) for p in catalogue()])
def product(path: str, query: dict[str, str]) -> Page | NotFound | None:
    item = lookup(query.get("id"))
    if item is None:
        return NotFound()
    return Page(
        title=f"{item.name} | Example",
        description=item.summary,
        params={"id": item.id},
        body=f"<h1>{item.name}</h1><p>{item.summary}</p>",
        jsonld=({"@context": "https://schema.org", "@type": "Product", "name": item.name},),
    )


app = FastAPI()
# ... your API routes ...
app.include_router(router(site, disallow=["/api/admin"]))  # mount last
```

That serves `/robots.txt`, `/sitemap.xml` and the SPA catch-all. Add `llms=` for
`/llms.txt` and `indexnow=` to publish an IndexNow key file.

Not using FastAPI? Everything underneath is a plain function:

```python
from crawlableseo import Page, render_shell, robots_txt, sitemap_xml
```

## What it does

- **Per-URL `<head>`** — title, description, canonical, robots, Open Graph,
  Twitter cards, and any number of JSON-LD objects.
- **Crawlable content** — HTML written into the mount node. Your framework
  replaces the node's children when it mounts, so users never see it; a crawler
  that does not run JavaScript reads it as the page.
- **`robots.txt`, `sitemap.xml`, `llms.txt`** — from the same declaration, so a
  page cannot be in one and missing from another.
- **IndexNow** — submit changed URLs to Bing (and through it, ChatGPT search)
  instead of waiting for the next crawl.
- **Honest status codes** — a URL with no content answers 404, not a 200 with an
  empty screen.

## What it does not do

- It never writes your copy. You supply the text; the library places it.
- It does not render your JavaScript. If a page's content exists only after a
  client-side fetch, give the resolver access to the same data on the server.
- It is not a meta-framework and will not become one.

## Bugs this prevents

Each of these was shipped to production on a live site before it was understood.
They are the reason the library exists, and every one has a test.

**A `<title>` mentioned in a build comment is not the title.** A shell carried a
comment explaining that the server rewrites `<title>`. A naive search-and-replace
matched that mention; the replacement ate the comment's closing `-->`, which
commented out the rest of `<head>` — stylesheet and bundle script included. The
site served a blank page with no console error and no failed request.

**Canonical and sitemap drift.** When the canonical tag and the sitemap entry are
built by two pieces of code, they disagree over a query parameter sooner or later,
and the two spellings become two pages with identical content. Here both come from
one function, and there is a test that fails if they ever differ.

**Blocking your own API starves the renderer.** `Disallow: /api/` in `robots.txt`
looks tidy. A crawler renders the page like a browser, so blocking the JSON the
app fetches leaves every route empty at render time. On one site that produced 22
soft 404s and 225 URLs stuck at "Discovered – currently not indexed". Disallow the
write and admin surfaces; leave the read-only data alone.

**`Content-Signal` costs more than it gives.** Lighthouse's `robots.txt` validator
does not know the directive, reports it as unknown, and takes points off the SEO
score of every page. Its absence already means no restriction, so this library has
no option to emit it.

**A `</` in your data closes the script tag.** One product name with a slash in it
and the JSON-LD block ends early, taking the rest of the document with it. Escaped
here, once.

**A backslash in a title raises a 500.** Titles built from query parameters can
contain anything; `re.sub` reads `\1` in a replacement string as a group
reference. An ordinary crafted URL becomes a server error.

**A 200 on an unknown path is a duplicate home page.** Every typo and stale link
becomes an indexable copy of your most important page. Unknown paths answer 404.

**`noindex` is not `nofollow`.** A page can be worth keeping out of the index while
its outgoing links are still worth crawling. They are separate flags.

**Do not detach the crawlable block early.** If you remove it before your framework
mounts, the page paints, empties, then repaints: on one site that measured a
cumulative layout shift of 0.28. Let the framework replace it.

## A build with no server

`prerender` writes the whole site out as files, so a static host serves the same
per-URL tags the server integration would:

```console
$ crawlableseo prerender --site app.seo:site --out dist
14 file(s) written
skipped /product: has query parameters; a static host cannot route them
```

One `index.html` per route (`/pricing` becomes `dist/pricing/index.html`, which
is what every static host serves at `/pricing`), plus `robots.txt` and
`sitemap.xml` from the same declaration. A URL that carries query parameters is
skipped and said out loud: no static host can route `/product?id=7`, and writing
a file nothing will ever serve would be worse than saying so.

## Check the shell before you ship it

```console
$ crawlableseo shell check dist/index.html
dist/index.html:7: error [E_MOUNT_NOT_EMPTY] <div id="root"> is not empty; the crawlable
  body is only written into an empty mount node
dist/index.html:5: warning [W_SHELL_CANONICAL] the shell already carries a canonical link
```

Every check comes from how the injection actually works, and every one of them
is invisible in a browser:

- **The mount node is not empty.** A loading spinner in the built markup means
  the crawlable body is never written - the fill only touches an empty node -
  and the page still looks perfect.
- **The shell was already rendered.** A build that captured one rendered page
  carries the marker, and then every URL serves that one page's tags.
- **No `<head>`, or no mount node at all.**
- **A canonical, robots meta or Open Graph tag already in the shell**, which the
  injected block will duplicate.
- **A `<base>` tag**, which changes what every relative URL in the injected block
  resolves to.

Point it at the built file, not at a URL. A served page legitimately has a
filled mount node and its own canonical, so the check says so rather than
reporting four problems that are not problems; `--as-shell` grades it anyway.

## Check an llms.txt

`llms.txt` is a map of the site written for models. A file that is malformed is
not read badly - it is read as nothing, silently, and the first sign is that no
model ever cites you.

```console
$ crawlableseo llms check https://example.com/llms.txt
https://example.com/llms.txt: valid llms.txt, nothing to report

$ crawlableseo llms check dist/llms.txt --strict
dist/llms.txt:7: warning [W_RELATIVE_URL] '/docs/start' is relative; this file is read
  on its own, with no page to resolve it against
dist/llms.txt:1 error(s), 1 warning(s)
```

It takes a path, an http(s) URL or `-` for standard input, prints `--json` for
CI, and exits non-zero on errors (`--strict` makes warnings count too).

Errors mean the file is not an llms.txt: no title, a second title, content
before the title, a link with no URL, a broken entry among links - and HTML,
which is what a site serves when the route was never added and the app's
catch-all answered instead. That last one is the commonest failure of all.

Warnings mean it is a valid file that will serve a model poorly: no summary
line, a link with no description, a relative URL in a file read on its own, a
duplicate URL or section, a section that lists nothing to fetch, an `## Optional`
section that is not last - everything after it is skipped with it.

What this library generates passes its own check; a test asserts it, because a
generator and a validator that disagree mean one of them is wrong.

## Compatibility

Python 3.10+. No required dependencies. `crawlableseo[indexnow]` adds `httpx`;
`crawlableseo[fastapi]` adds FastAPI for the router.

## License

MIT
