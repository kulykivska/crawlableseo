"""Two commands for a build that has no server.

`prerender` writes the site out as files; `shell check` says what will go wrong
when a shell is filled. Both exist because the failure they catch is invisible
in a browser: the page looks right, and the crawler gets nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crawlableseo import DynamicUrl, Page, Site
from crawlableseo.cli import main
from crawlableseo.findings import is_valid
from crawlableseo.prerender import file_for, prerender
from crawlableseo.shellcheck import check_shell

SHELL = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width'>"
    "<title>App</title><meta name='description' content='x'>"
    "</head><body><div id='root'></div></body></html>"
)


def build_site() -> Site:
    site = Site(
        "https://example.com",
        shell_html=SHELL,
        name="Example",
        default_title="Example",
        default_description="A site with a description long enough to be useful.",
    )
    site.page(
        "/", title="Home | Example", description="The home page of Example.", body="<h1>Hi</h1>"
    )
    site.page(
        "/pricing", title="Pricing | Example", description="Three plans and what they cost."
    )
    return site


def codes(html: str, **kwargs: str) -> list[str]:
    return [f.code for f in check_shell(html, **kwargs)]


# --- prerender ------------------------------------------------------------


def test_each_route_becomes_a_file_a_static_host_serves(tmp_path: Path) -> None:
    result = prerender(build_site(), tmp_path)
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "pricing" / "index.html").exists()
    assert "robots.txt" in result.written
    assert "sitemap.xml" in result.written


def test_the_written_file_carries_that_route_s_own_tags(tmp_path: Path) -> None:
    """The whole point: every file used to be the same document."""
    prerender(build_site(), tmp_path)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    pricing = (tmp_path / "pricing" / "index.html").read_text(encoding="utf-8")
    assert "<title>Home | Example</title>" in home
    assert "<title>Pricing | Example</title>" in pricing
    assert '<link rel="canonical" href="https://example.com/pricing"' in pricing
    assert "<h1>Hi</h1>" in home


def test_a_url_with_query_parameters_is_skipped_and_said_so(tmp_path: Path) -> None:
    """A static host cannot answer /product?id=7 with a file of its own, and
    writing one anyway would be a file nothing ever serves."""
    site = build_site()

    @site.dynamic("/product", urls=lambda: [DynamicUrl("/product", {"id": "7"})])
    def product(path: str, query: dict[str, str]) -> Page:
        return Page(title="Product", description="A product page with a description.")

    result = prerender(site, tmp_path)
    assert result.skipped == [
        ("/product", "has query parameters; a static host cannot route them")
    ]
    assert not (tmp_path / "product").exists()


def test_a_path_only_dynamic_route_is_written(tmp_path: Path) -> None:
    site = build_site()

    @site.dynamic("/guide", urls=lambda: [DynamicUrl("/guide/setup")])
    def guide(path: str, query: dict[str, str]) -> Page:
        return Page(
            title="Setup | Example", description="How to set Example up in ten minutes."
        )

    prerender(site, tmp_path)
    written = (tmp_path / "guide" / "setup" / "index.html").read_text(encoding="utf-8")
    assert "<title>Setup | Example</title>" in written


def test_a_route_that_resolves_to_an_error_is_not_written(tmp_path: Path) -> None:
    site = build_site()
    site.noindex("/admin")
    site.page("/admin", title="Admin", description="Not for crawlers.", index=False)
    result = prerender(site, tmp_path)
    # noindex is not 404: the page is written, and its robots tag says noindex.
    admin = (tmp_path / "admin" / "index.html").read_text(encoding="utf-8")
    assert "noindex" in admin
    assert result.skipped == []


@pytest.mark.parametrize(
    ("path", "expected"),
    [("/", "index.html"), ("/pricing", "pricing/index.html"), ("/a/b", "a/b/index.html")],
)
def test_the_file_layout_is_what_a_static_host_expects(path: str, expected: str) -> None:
    assert file_for(Path("out"), path) == Path("out") / expected


def test_robots_and_sitemap_can_be_left_out(tmp_path: Path) -> None:
    prerender(build_site(), tmp_path, robots=False, sitemap=False)
    assert not (tmp_path / "robots.txt").exists()
    assert not (tmp_path / "sitemap.xml").exists()


def test_the_command_prerenders_an_imported_site(tmp_path: Path, monkeypatch, capsys) -> None:
    module = tmp_path / "mysite.py"
    module.write_text(
        "from crawlableseo import Site\n"
        f"site = Site('https://example.com', shell_html={SHELL!r}, name='Example')\n"
        "site.page('/', title='Home', description='The home page of Example.')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["prerender", "--site", "mysite:site", "--out", "dist"]) == 0
    assert (tmp_path / "dist" / "index.html").exists()
    assert "file(s) written" in capsys.readouterr().out


def test_a_site_that_is_not_there_is_named(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["prerender", "--site", "empty:site", "--out", "dist"]) == 2
    assert "no attribute 'site'" in capsys.readouterr().err


# --- shell check ----------------------------------------------------------


def test_a_good_shell_says_nothing() -> None:
    assert check_shell(SHELL) == []
    assert is_valid(check_shell(SHELL), strict=True)


def test_a_mount_node_with_content_in_it_is_an_error() -> None:
    """The fill only touches an empty node, so a loading spinner in the markup
    means the crawlable body is dropped - silently, and the page looks fine."""
    html = SHELL.replace("<div id='root'></div>", "<div id='root'>loading…</div>")
    assert "E_MOUNT_NOT_EMPTY" in codes(html)


def test_a_missing_mount_node_is_an_error() -> None:
    html = SHELL.replace("<div id='root'></div>", "<div id='app'></div>")
    assert "E_NO_MOUNT" in codes(html)
    assert codes(html, mount_id="app") == []


def test_a_shell_that_was_already_rendered_is_an_error() -> None:
    """render_shell leaves a marked document alone, so a build that captured
    one rendered page would serve those tags on every URL."""
    marked = SHELL.replace("</head>", "<!-- crawlableseo --></head>")
    assert "E_ALREADY_RENDERED" in codes(marked)


def test_a_document_with_no_head_is_an_error() -> None:
    assert "E_NO_HEAD" in codes("<html><body><div id='root'></div></body></html>")


def test_an_empty_file_is_an_error() -> None:
    assert codes("   ") == ["E_EMPTY"]


def test_a_canonical_already_in_the_shell_is_reported() -> None:
    html = SHELL.replace("</head>", "<link rel='canonical' href='https://example.com/'></head>")
    assert "W_SHELL_CANONICAL" in codes(html)


def test_a_title_that_exists_only_inside_a_comment_is_reported() -> None:
    """The bug this library was written for, seen from the other side."""
    comment = "<!-- <title>App</title> is set by the server -->"
    html = SHELL.replace("<title>App</title>", comment)
    assert "W_TITLE_ONLY_IN_COMMENT" in codes(html)


def test_a_base_tag_changes_what_the_injected_links_mean() -> None:
    assert "W_BASE_TAG" in codes(SHELL.replace("<head>", "<head><base href='/app/'>"))


def test_the_command_reports_and_exits(tmp_path: Path, capsys) -> None:
    good = tmp_path / "good.html"
    good.write_text(SHELL, encoding="utf-8")
    assert main(["shell", "check", str(good)]) == 0
    assert "valid shell" in capsys.readouterr().out

    bad = tmp_path / "bad.html"
    bad.write_text(SHELL.replace("<div id='root'></div>", "<div id='root'>x</div>"), "utf-8")
    assert main(["shell", "check", str(bad)]) == 1
    assert "E_MOUNT_NOT_EMPTY" in capsys.readouterr().out


def test_the_mount_id_is_configurable_from_the_command(tmp_path: Path) -> None:
    path = tmp_path / "shell.html"
    path.write_text(SHELL.replace("id='root'", "id='app'"), encoding="utf-8")
    assert main(["shell", "check", str(path)]) == 1
    assert main(["shell", "check", str(path), "--mount-id", "app"]) == 0


RENDERED = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Pricing | Example</title><meta name='description' content='Plans.'>"
    "<link rel='canonical' href='https://example.com/pricing'>"
    "<meta property='og:title' content='Pricing'>"
    "</head><body><div id='root'><h1>Pricing</h1><p>" + ("Plans and prices. " * 40) + "</p>"
    "</div></body></html>"
)


def test_a_served_page_is_not_graded_as_a_shell() -> None:
    """Running the check on a URL is the obvious thing to do, and a served page
    legitimately has a filled mount node and its own canonical. Grading that as
    a shell reports four problems that are not problems."""
    findings = check_shell(RENDERED)
    assert [f.code for f in findings] == ["W_NOT_A_SHELL"]
    assert "dist/index.html rather than a URL" in findings[0].message


def test_a_shell_with_a_spinner_is_still_graded_as_a_shell() -> None:
    """A loading state is short; a rendered page is not. The line between them
    is what tells a build's shell from a served page."""
    html = SHELL.replace("<div id='root'></div>", "<div id='root'><p>Loading…</p></div>")
    assert "E_MOUNT_NOT_EMPTY" in codes(html)


def test_as_shell_grades_it_anyway() -> None:
    findings = check_shell(RENDERED, as_shell=True)
    assert "E_MOUNT_NOT_EMPTY" in [f.code for f in findings]


def test_the_command_takes_as_shell(tmp_path: Path, capsys) -> None:
    path = tmp_path / "page.html"
    path.write_text(RENDERED, encoding="utf-8")
    assert main(["shell", "check", str(path)]) == 0
    assert "W_NOT_A_SHELL" in capsys.readouterr().out
    assert main(["shell", "check", str(path), "--as-shell"]) == 1
