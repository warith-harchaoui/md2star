"""md2star — typed exceptions for the CLI / pipeline.

Two purposes:

1. **Carry an actionable hint.** Every subclass takes a ``hint=``
   keyword whose string is printed below the headline error so the
   user knows what to *do*, not just what went wrong. The CLI's
   top-level handler renders this as a multi-line block (see
   :func:`md2star.cli.handle_known_error`) instead of a Python
   stacktrace.
2. **Mark which failures are "expected".** Anything that subclasses
   :class:`Md2starError` is something we predicted and want to
   render cleanly. Anything else genuinely is a bug and the CLI
   re-raises with the original traceback so the user can file an
   issue.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations


class Md2starError(Exception):
    """Base class for every md2star-defined, user-actionable error.

    The CLI top-level handler renders these with the ``hint`` string
    on a second line and exits non-zero. Subclasses set a sensible
    ``hint`` default so callers don't have to repeat the boilerplate.
    """

    # Class-level default carried by every subclass; a subclass overrides it by
    # simply redeclaring ``default_hint``. This is why the concrete errors below
    # are one-liners — they inherit all behaviour and only swap this string.
    default_hint: str = ""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        # ``hint`` is keyword-only (the ``*``) so call sites read self-
        # documenting: ``raise InvalidInputError(msg, hint=...)``. An explicit
        # ``hint=""`` is respected; only ``None`` (the default) falls back to
        # the class default, so a caller can deliberately suppress the hint.
        self.hint = hint if hint is not None else self.default_hint


# ── Concrete errors ──────────────────────────────────────────────────────
# Each subclass below is intentionally minimal: its *type* is the signal the
# CLI switches on (e.g. MissingDependencyError → exit 127), and its
# ``default_hint`` is the actionable text shown under the headline. The
# docstrings explain *when* each fires; there is no behaviour to add.


class MissingDependencyError(Md2starError):
    """Required external program (pandoc, soffice, node, …) not found on PATH.

    Raised when md2star is about to invoke a system binary that is not
    installed. Carries the binary name and the suggested install
    command.
    """

    default_hint = (
        "Run `md2star doctor` for a full environment report and install "
        "instructions per platform."
    )


class TemplateNotFoundError(Md2starError):
    """Requested reference template (template.docx / template.pptx) not located.

    Distinct from a missing *bundled* template (which is a
    :class:`MissingDependencyError` because it means the wheel is
    corrupted). This one fires when the user asks for a template that
    isn't where they said it'd be.
    """

    default_hint = (
        "Run `md2star templates list` to see which templates are "
        "discoverable, or pass --reference-doc /path/to/template.docx "
        "explicitly."
    )


class RemoteResourceDisabledError(Md2starError):
    """An online fetch was needed but blocked by --offline or the default policy.

    By default md2star refuses to reach the network. The CLI surfaces
    this with a hint that names the relevant opt-in flag
    (``--allow-remote-images`` / ``--allow-remote-templates``).
    """

    default_hint = (
        "md2star runs offline by default. Use --allow-remote-images "
        "or --allow-remote-templates to opt in, OR --offline to make "
        "the rejection explicit in scripts."
    )


class ConversionError(Md2starError):
    """Pandoc / soffice / mermaid-cli exited non-zero.

    Wraps the failing subprocess's stderr so the user sees the real
    cause without us re-rendering a Python traceback.
    """

    default_hint = (
        "If the failure mentions a missing engine (xelatex, soffice, "
        "mmdc), install it and re-run. Otherwise the file `--verbose` "
        "above contains the full pandoc / soffice stderr."
    )


class InvalidInputError(Md2starError):
    """Input file doesn't exist, isn't readable, or has a wrong extension."""

    default_hint = (
        "md2star accepts a single .md / .markdown file. Pass the path "
        "as the first positional argument."
    )


class UnsafePathError(Md2starError):
    """Filesystem path escapes the operation's sandbox (GUI folder browser)."""

    default_hint = (
        "Paths supplied to the GUI's /fs/* endpoints must stay inside "
        "the open folder root. `..` segments, absolute paths, and "
        "symlinks that resolve outside the root are rejected."
    )


# Explicit public surface: ``from md2star.errors import *`` re-exports only
# these names, and it documents the intended API for downstream importers.
__all__ = [
    "Md2starError",
    "MissingDependencyError",
    "TemplateNotFoundError",
    "RemoteResourceDisabledError",
    "ConversionError",
    "InvalidInputError",
    "UnsafePathError",
]
