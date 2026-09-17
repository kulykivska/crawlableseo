"""The injection marker, in its own module so head and shell can share it."""

from __future__ import annotations

# Marks a shell that has already been injected, so a second pass is a no-op
# rather than a document carrying two canonicals.
MARKER = "<!-- crawlableseo -->"
