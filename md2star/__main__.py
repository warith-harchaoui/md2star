"""Allow ``python -m md2star`` as an alternative to the ``md2star`` console script.

Module summary
--------------
Thin shim that forwards ``python -m md2star`` invocations to
:func:`md2star.cli.main`. Python convention: every importable
package that exposes a CLI should be runnable via ``-m``, so users
who bypass the installed entry point (debugging, sandboxed Pythons,
`pipx run --spec md2star md2star` style invocations) still get the
same behaviour.

Usage
-----
>>> # From the shell:
>>> #   python -m md2star --help
>>> #   python -m md2star docx report.md
>>> # is equivalent to the installed `md2star` entry point.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
