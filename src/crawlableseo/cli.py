"""The `crawlableseo` command.

Grouped by what it acts on, so the next commands - a shell check, a
prerender - sit beside these rather than lengthening one list of verbs.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .llmscheck import ERROR, WARNING, Finding, check_llms_txt, is_valid

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


def _report(target: str, findings: list[Finding], *, strict: bool, as_json: bool) -> int:
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
        print(f"{target}: valid llms.txt, nothing to report")
    else:
        print(f"{target}: {errors} error(s), {warnings} warning(s)")
    return EXIT_OK if passed else EXIT_FAILED


def _llms_check(args: argparse.Namespace) -> int:
    try:
        text = read_target(args.target)
    except (OSError, urllib.error.URLError) as exc:
        print(f"{args.target}: cannot read: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    return _report(args.target, check_llms_txt(text), strict=args.strict, as_json=args.json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawlableseo", description=__doc__)
    parser.add_argument("--version", action="version", version=f"crawlableseo {__version__}")
    groups = parser.add_subparsers(dest="group", required=True)

    llms = groups.add_parser("llms", help="the llms.txt file").add_subparsers(
        dest="command", required=True
    )
    check = llms.add_parser("check", help="validate an llms.txt file or URL")
    check.add_argument("target", help="path, http(s) URL, or - for stdin")
    check.add_argument(
        "--strict", action="store_true", help="fail on warnings as well as errors"
    )
    check.add_argument("--json", action="store_true", help="machine-readable output")
    check.set_defaults(func=_llms_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
