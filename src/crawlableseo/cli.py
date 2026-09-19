"""The `crawlableseo` command.

Grouped by what it acts on, so the next commands - a shell check, a
prerender - sit beside these rather than lengthening one list of verbs.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .findings import ERROR, WARNING, Finding, is_valid
from .llmscheck import check_llms_txt
from .prerender import prerender
from .shellcheck import check_shell

# Fetching is stdlib only: a validator that pulls in an HTTP client is a
# dependency everyone who only validates files pays for.
FETCH_TIMEOUT = 15
MAX_FETCH_BYTES = 5 * 1024 * 1024
# How many of one code to print before summarising the rest.
PER_CODE = 10

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_UNUSABLE = 2


def read_target(target: str) -> str:
    """A path, a URL, or `-` for standard input."""
    if target == "-":
        return sys.stdin.read()
    if target.startswith(("http://", "https://")):
        # The scheme is checked above, so this never opens file:// or data://.
        request = urllib.request.Request(
            target,
            headers={"User-Agent": f"crawlableseo/{__version__} (llms.txt check)"},
        )
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            body: bytes = response.read(MAX_FETCH_BYTES)
        return body.decode("utf-8", errors="replace")
    return Path(target).read_text(encoding="utf-8")


def _report(
    target: str,
    findings: list[Finding],
    *,
    strict: bool,
    as_json: bool,
    subject: str = "llms.txt",
) -> int:
    passed = is_valid(findings, strict=strict)
    if as_json:
        print(
            json.dumps(
                {
                    "target": target,
                    "ok": passed,
                    "findings": [
                        {"level": f.level, "code": f.code, "line": f.line, "message": f.message}
                        for f in findings
                    ],
                },
                indent=2,
            )
        )
        return EXIT_OK if passed else EXIT_FAILED

    shown: dict[str, int] = {}
    for finding in findings:
        shown[finding.code] = shown.get(finding.code, 0) + 1
        if shown[finding.code] > PER_CODE:
            continue
        where = finding.line or "-"
        print(f"{target}:{where}: {finding.level} [{finding.code}] {finding.message}")
    for code, count in shown.items():
        # A file with five hundred of one warning should not scroll the rest away.
        if count > PER_CODE:
            print(f"{target}: ... and {count - PER_CODE} more [{code}]")
    errors = sum(1 for f in findings if f.level == ERROR)
    warnings = sum(1 for f in findings if f.level == WARNING)
    if not findings:
        print(f"{target}: valid {subject}, nothing to report")
    else:
        print(f"{target}: {errors} error(s), {warnings} warning(s)")
    return EXIT_OK if passed else EXIT_FAILED


def load_site(spec: str) -> object:
    """Import `module:attribute`, the way a WSGI server names an app.

    The declaration is Python - it has to be, because a dynamic route is a
    function - so a command that prerenders it has to import it.
    """
    module_name, _, attribute = spec.partition(":")
    if not attribute:
        raise ValueError(f"{spec!r} must be module:attribute, e.g. app.seo:site")
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attribute)
    except AttributeError:
        raise ValueError(f"{module_name} has no attribute {attribute!r}") from None


def _prerender(args: argparse.Namespace) -> int:
    site = load_site(args.site)
    result = prerender(
        site,  # type: ignore[arg-type]
        Path(args.out),
        robots=not args.no_robots,
        sitemap=not args.no_sitemap,
    )
    print(result.describe())
    return EXIT_OK


def _shell_check(args: argparse.Namespace) -> int:
    try:
        text = read_target(args.target)
    except (OSError, urllib.error.URLError) as exc:
        print(f"{args.target}: cannot read: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    findings = check_shell(text, mount_id=args.mount_id, as_shell=args.as_shell)
    return _report(
        args.target, findings, strict=args.strict, as_json=args.json, subject="shell"
    )


def _llms_check(args: argparse.Namespace) -> int:
    try:
        text = read_target(args.target)
    except (OSError, urllib.error.URLError) as exc:
        print(f"{args.target}: cannot read: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    return _report(args.target, check_llms_txt(text), strict=args.strict, as_json=args.json)


def _add_check_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--strict", action="store_true", help="fail on warnings as well as errors"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawlableseo", description=__doc__)
    parser.add_argument("--version", action="version", version=f"crawlableseo {__version__}")
    groups = parser.add_subparsers(dest="group", required=True)

    llms = groups.add_parser("llms", help="the llms.txt file").add_subparsers(
        dest="command", required=True
    )
    check = llms.add_parser("check", help="validate an llms.txt file or URL")
    check.add_argument("target", help="path, http(s) URL, or - for stdin")
    _add_check_flags(check)
    check.set_defaults(func=_llms_check)

    shell = groups.add_parser("shell", help="the built HTML shell").add_subparsers(
        dest="command", required=True
    )
    shell_check = shell.add_parser(
        "check", help="what will go wrong when this shell is filled"
    )
    shell_check.add_argument("target", help="path, http(s) URL, or - for stdin")
    shell_check.add_argument("--mount-id", default="root", help="id of the mount node")
    shell_check.add_argument(
        "--as-shell",
        action="store_true",
        help="grade it as a shell even if it looks like an already-filled page",
    )
    _add_check_flags(shell_check)
    shell_check.set_defaults(func=_shell_check)

    pre = groups.add_parser("prerender", help="write the site out as files for a static host")
    pre.add_argument("--site", required=True, help="module:attribute holding the Site")
    pre.add_argument("--out", required=True, help="directory to write into")
    pre.add_argument("--no-robots", action="store_true")
    pre.add_argument("--no-sitemap", action="store_true")
    pre.set_defaults(func=_prerender)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result: int = args.func(args)
    except (OSError, ValueError, ImportError) as exc:
        # A missing module, a site that is not where it was said to be, an
        # unreadable file: the operator's problem to fix, not a traceback.
        print(f"{exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
