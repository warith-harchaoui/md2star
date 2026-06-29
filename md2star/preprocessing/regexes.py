"""Shared compiled regexes used across the preprocessing pipeline.

The members of this module are intentionally public (no leading underscore)
because they are imported by several sibling modules. Centralising them here
removes the cross-module private-symbol smell where, for example,
``pipeline.py`` reached into ``images.py`` for ``_PIPE_TABLE_ROW_RE``.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re

# A pipe-table row: a line that starts (after optional whitespace) with ``|``.
# Deliberately permissive — used as a fast filter; the table-block walker
# then verifies the separator row before treating the block as a table.
PIPE_TABLE_ROW_RE = re.compile(r"^\s*\|")
