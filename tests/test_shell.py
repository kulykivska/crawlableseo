"""Shell injection, and the ways it has gone wrong on real sites."""

from __future__ import annotations

import re

from crawlableseo import MARKER, Page, render_shell

SHELL = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Fallback</title>
    <meta name="description" content="fallback" />
    <script type="module" src="/assets/index-abc.js"></script>
  </head>
  <body><div id="root"></div></body>
</html>
"""


def render(page: Page, shell: str = SHELL, **kwargs: object) -> str:
    return render_shell(
        shell,
        page,
        canonical="https://example.com/x",
        base_url="https://example.com",
        **kwargs,  # type: ignore[arg-type]
    )


def title_of(out: str) -> str:
    return re.search(r"<title>(.*?)</title>", out, re.DOTALL).group(1)  # type: ignore[union-attr]


def test_title_and_description_are_replaced():
    out = render(Page(title="Real title", description="Real description"))
    assert title_of(out) == "Real title"
    assert 'content="Real description"' in out
    assert "fallback" not in out


def test_a_title_named_inside_a_comment_is_not_the_title():
    """Shipped once as a blank site.

    The shell carried a build comment explaining that the server rewrites
    ``<title>``. A naive search found that mention, the replacement ate the
    comment's closing marker, and everything after it - stylesheet, bundle
    script - became comment text. No console error, no failed request,
    nothing rendered.
    """
    shell = SHELL.replace(
        "    <title>Fallback</title>",
        "    <!-- The server rewrites <title> and <meta name=description>. -->\n"
        "    <title>Fallback</title>",
    )
    out = render(Page(title="Real title", description="Real description"), shell)

    assert "<title>Real title</title>" in out
    assert "<title>Fallback</title>" not in out
    # The comment itself is untouched, mention of the tag and all.
    assert "The server rewrites <title>" in out
    # The comment still opens and closes, and the bundle is a live tag.
    assert out.count("<!--") == out.count("-->")
    assert '<script type="module" src="/assets/index-abc.js">' in out


def test_shell_without_a_title_gets_one():
    shell = SHELL.replace("    <title>Fallback</title>\n", "")
    out = render(Page(title="Added", description="Added description"))
    assert title_of(out) == "Added"
    assert "</head>" in out
    out = render(Page(title="Added", description="Added description"), shell)
    assert title_of(out) == "Added"


def test_a_backslash_in_the_title_does_not_raise():
    """A title built from a query parameter can contain anything.

    With a plain string replacement, re reads ``\\1`` as a group reference
    and raises: an ordinary crafted URL becomes a 500.
    """
    out = render(Page(title=r"Race \1 \g<0> results", description="d"))
    assert r"Race \1 \g&lt;0&gt; results" in out


def test_injection_is_idempotent():
    once = render(Page(title="T", description="D"))
    twice = render(Page(title="T", description="D"), once)
    assert once == twice
    assert once.count(MARKER) == 1
    assert once.count('rel="canonical"') == 1


def test_crawlable_body_goes_inside_the_mount_node():
    out = render(Page(title="T", description="D", body="<h1>Real text</h1>"))
    assert '<div id="root"><h1>Real text</h1></div>' in out


def test_body_is_left_out_when_the_mount_node_is_missing():
    shell = SHELL.replace('<div id="root"></div>', "<div id=app></div>")
    out = render(Page(title="T", description="D", body="<h1>x</h1>"), shell)
    assert "<h1>x</h1>" not in out


def test_json_ld_cannot_close_the_script_tag():
    page = Page(
        title="T",
        description="D",
        jsonld=({"@type": "Thing", "name": "</script><img onerror=alert(1)>"},),
    )
    out = render(page)
    assert "</script><img" not in out
    assert "<\\/script>" in out


def test_long_values_are_cut_where_the_tags_are_written():
    page = Page(title="T" * 200, description="D" * 400)
    out = render(page)
    assert len(title_of(out)) <= 60
    desc = re.search(r'name="description" content="(.*?)"', out).group(1)  # type: ignore[union-attr]
    assert len(desc) <= 160


def test_noindex_can_still_be_follow():
    out = render(Page(title="T", description="D", index=False, follow=True))
    assert 'content="noindex, follow"' in out
    out = render(Page(title="T", description="D", index=False, follow=False))
    assert 'content="noindex, nofollow"' in out


def test_relative_og_image_is_made_absolute():
    out = render(Page(title="T", description="D", og_image="/card.png"))
    assert 'content="https://example.com/card.png"' in out
