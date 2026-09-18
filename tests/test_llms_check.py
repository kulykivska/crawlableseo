"""Reading an llms.txt back.

The two properties that matter: a file this library generates passes its own
check, and every rule fires on a file that breaks it. A validator nobody can
make fail is a validator nobody should trust.
"""

from __future__ import annotations

import json

import pytest

from crawlableseo import LlmsSection, check_llms_txt, is_valid, llms_txt
from crawlableseo.cli import main

GOOD = """# Northwind

> Northwind builds weather stations for small farms.

## Docs

- [Getting started](https://northwind.example/docs/start): install it and read one sensor.
- [API reference](https://northwind.example/docs/api): every endpoint, with examples.

## Optional

- [Changelog](https://northwind.example/changelog): what shipped, most recent first.
"""


def codes(text: str) -> list[str]:
    return [f.code for f in check_llms_txt(text)]


def test_a_good_file_says_nothing():
    assert check_llms_txt(GOOD) == []
    assert is_valid(check_llms_txt(GOOD), strict=True)


def test_what_this_library_generates_passes_its_own_check():
    """The generator and the validator must agree, or one of them is wrong."""
    text = llms_txt(
        "Northwind",
        "Northwind builds weather stations for small farms.",
        [
            LlmsSection(
                "Docs",
                [
                    ("Getting started", "https://northwind.example/docs/start", "Install it."),
                    ("API reference", "https://northwind.example/docs/api", "Every endpoint."),
                ],
            )
        ],
    )
    assert check_llms_txt(text) == []


def test_an_empty_file_is_an_error():
    assert codes("   \n\n") == ["E_EMPTY"]


def test_html_served_at_the_llms_route_is_named_for_what_it_is():
    """The commonest failure by far: the route was never added and the SPA's
    catch-all answered with index.html."""
    findings = check_llms_txt("<!doctype html>\n<html><head><title>App</title></head></html>")
    assert [f.code for f in findings] == ["E_HTML"]
    assert "falling through to the app" in findings[0].message


def test_a_file_with_no_title_fails():
    assert "E_NO_H1" in codes("> a summary with nothing above it\n")


def test_content_before_the_title_fails():
    assert "E_H1_NOT_FIRST" in codes("Some prose first.\n\n# Northwind\n")


def test_a_second_title_fails():
    assert "E_MULTIPLE_H1" in codes("# Northwind\n\n# Northwind again\n")


def test_a_bad_entry_among_links_fails():
    text = (
        "# N\n\n> s\n\n## Docs\n\n- [A](https://e.example/a): d\n"
        "- just some text\n"
    )
    assert "E_BAD_LINK" in codes(text)


def test_a_section_of_bulleted_prose_is_advice_not_an_error():
    """Real files use bullets for notes inside a section. It is worth saying
    that a model gets nothing to fetch there; it is not a broken file."""
    findings = check_llms_txt("# N\n\n> s\n\n## Languages\n\n- English - 629 pages\n")
    assert [f.code for f in findings] == ["W_PROSE_BULLETS"]


def test_a_dash_separates_a_description_as_well_as_a_colon():
    text = "# N\n\n> s\n\n## Docs\n\n- [Overview](https://e.example/a) - what it covers\n"
    assert check_llms_txt(text) == []


def test_a_link_with_no_url_fails():
    text = "# N\n\n> s\n\n## Docs\n\n- [Start](): install it\n"
    assert "E_EMPTY_URL" in codes(text)


def test_a_bullet_outside_a_section_is_left_alone():
    """Prose between the summary and the first section is allowed, and a list
    in it is prose, not a broken link."""
    text = (
        "# N\n\n> s\n\n- a plain list item in the prose\n\n"
        "## Docs\n\n- [S](https://e.example/s): d\n"
    )
    assert "E_BAD_LINK" not in codes(text)


@pytest.mark.parametrize(
    ("code", "text"),
    [
        ("W_NO_SUMMARY", "# Northwind\n\n## Docs\n\n- [S](https://e.example/s): d\n"),
        ("W_NO_SECTIONS", "# Northwind\n\n> a summary\n"),
        ("W_NO_DESCRIPTION", "# N\n\n> s\n\n## Docs\n\n- [Start](https://e.example/s)\n"),
        ("W_RELATIVE_URL", "# N\n\n> s\n\n## Docs\n\n- [Start](/docs/start): d\n"),
        (
            "W_DUPLICATE_URL",
            "# N\n\n> s\n\n## Docs\n\n"
            "- [A](https://e.example/s): d\n- [B](https://e.example/s): d\n",
        ),
        (
            "W_EMPTY_SECTION",
            "# N\n\n> s\n\n## Docs\n\n## More\n\n- [A](https://e.example/a): d\n",
        ),
        (
            "W_DUPLICATE_SECTION",
            "# N\n\n> s\n\n## Docs\n\n- [A](https://e.example/a): d\n\n## Docs\n\n"
            "- [B](https://e.example/b): d\n",
        ),
        (
            "W_DEEP_HEADING",
            "# N\n\n> s\n\n## Docs\n\n### Deeper\n\n- [A](https://e.example/a): d\n",
        ),
        ("W_EMPTY_TITLE", "#\n\n> s\n\n## Docs\n\n- [A](https://e.example/a): d\n"),
    ],
)
def test_each_warning_fires(code: str, text: str):
    assert code in codes(text)


def test_optional_must_be_last_or_it_hides_what_follows():
    text = (
        "# N\n\n> s\n\n## Optional\n\n- [A](https://e.example/a): d\n\n"
        "## Docs\n\n- [B](https://e.example/b): d\n"
    )
    assert "W_OPTIONAL_NOT_LAST" in codes(text)


def test_warnings_pass_unless_asked_about():
    findings = check_llms_txt("# Northwind\n\n## Docs\n\n- [S](https://e.example/s): d\n")
    assert is_valid(findings)
    assert not is_valid(findings, strict=True)


def test_findings_are_ordered_by_line():
    text = "# N\n\n## Docs\n\n- [A](/a)\n- [B](/b)\n"
    lines = [f.line for f in check_llms_txt(text)]
    assert lines == sorted(lines)


def test_the_command_reports_a_good_file(tmp_path, capsys):
    path = tmp_path / "llms.txt"
    path.write_text(GOOD, encoding="utf-8")
    assert main(["llms", "check", str(path)]) == 0
    assert "valid llms.txt" in capsys.readouterr().out


def test_the_command_fails_on_an_error(tmp_path, capsys):
    path = tmp_path / "llms.txt"
    path.write_text("<html></html>", encoding="utf-8")
    assert main(["llms", "check", str(path)]) == 1
    assert "E_HTML" in capsys.readouterr().out


def test_strict_turns_advice_into_failure(tmp_path):
    path = tmp_path / "llms.txt"
    path.write_text("# N\n\n## Docs\n\n- [S](https://e.example/s): d\n", encoding="utf-8")
    assert main(["llms", "check", str(path)]) == 0
    assert main(["llms", "check", str(path), "--strict"]) == 1


def test_json_output_is_machine_readable(tmp_path, capsys):
    path = tmp_path / "llms.txt"
    path.write_text("# N\n\n## Docs\n\n- [S](/s)\n", encoding="utf-8")
    main(["llms", "check", str(path), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert {f["code"] for f in report["findings"]} >= {"W_RELATIVE_URL", "W_NO_DESCRIPTION"}


def test_a_missing_file_is_an_unusable_target(tmp_path, capsys):
    assert main(["llms", "check", str(tmp_path / "nope.txt")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_stdin_is_a_target(monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(GOOD))
    assert main(["llms", "check", "-"]) == 0


def test_a_url_target_is_fetched(monkeypatch):
    """No network in the suite: the fetch is the thing under test, not urllib."""
    calls: list[str] = []

    class FakeResponse:
        def read(self, _limit: int) -> bytes:
            return GOOD.encode()

        def __enter__(self):
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        calls.append(request.full_url)
        assert "crawlableseo/" in request.headers["User-agent"]
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert main(["llms", "check", "https://northwind.example/llms.txt"]) == 0
    assert calls == ["https://northwind.example/llms.txt"]
