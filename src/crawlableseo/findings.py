"""What a check reports, shared by every check in this package.

Errors mean the thing is broken. Warnings mean it works and will serve a
crawler, or a model, worse than it could.
"""

from __future__ import annotations

from dataclasses import dataclass

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    line: int
    message: str

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line else "file"
        return f"{where}: {self.level} [{self.code}] {self.message}"


def is_valid(findings: list[Finding], *, strict: bool = False) -> bool:
    """Whether the file passes. Warnings only count when asked for."""
    levels = {f.level for f in findings}
    if ERROR in levels:
        return False
    return not (strict and WARNING in levels)


def line_of(text: str, index: int) -> int:
    """1-based line number of an offset, for a finding that points at markup."""
    return text.count("\n", 0, index) + 1
