"""Functional tests for the v1.2.0 offline / remote-resource security policy.

The contract these tests defend:

* By default md2star does NOT download remote *images*. Remote images
  are left in place and a warning points at the opt-in flag.
* ``--allow-remote-images`` opts in to ``download_remote_images``.
* Since v2.5.0 the deraison.ai reference *template* is fetched by
  DEFAULT when no local ``template.{docx,pptx}`` exists; the opt-out is
  ``--no-remote-templates`` (``allow_remote_templates=False``).
* ``--offline`` is the hard kill-switch: it forces every network / LLM
  side-effect off (images, templates, lint, alt-text) and silences the
  soft-refuse warning — even when the ``allow_*`` flags are also present.

Each *security gate* keeps its own test so a regression names the exact
gate it broke. Value-families (allowed vs. default, etc.) are folded as
in-body loops rather than dropped. Assertions run at the API level
(``preprocess_markdown`` + ``_resolve_reference_doc``) so they're
independent of the CLI's argparse layer.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from md2star.preprocessing import preprocess_markdown

MD_WITH_REMOTE_IMG = "Some prose.\n\n![hero](https://example.invalid/banner.png)\n\nMore prose.\n"
MD_WITH_LOCAL_IMG = "Some prose.\n\n![local](./images/foo.png)\n\nMore prose.\n"


# ─────────────────────────────────────────────────────────────────────
# preprocess_markdown — remote-image policy
# ─────────────────────────────────────────────────────────────────────


def test_remote_image_soft_refuse_warning_behaviour(caplog):
    """The default-deny warning fires only when there is a remote image to refuse.

    Three facets in one run: (1) by default the remote URL is preserved verbatim
    and an actionable warning names the URL + opt-in flag; (2) a local-only doc
    logs no warning (no false positive); (3) an explicit ``--offline`` silences
    the nudge as noise (the refusal is already intentional).
    """
    # Default deny: URL survives, warning names the URL and the opt-in flag.
    caplog.set_level(logging.WARNING, logger="md2star")
    result = preprocess_markdown(MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False)
    assert "https://example.invalid/banner.png" in result
    assert "--allow-remote-images" in caplog.text
    assert "https://example.invalid/banner.png" in caplog.text

    # Local-only document: no remote-skip warning at all.
    caplog.clear()
    preprocess_markdown(MD_WITH_LOCAL_IMG, inject_metadata=False, lint_enabled=False)
    assert "--allow-remote-images" not in caplog.text

    # Explicit --offline: the nudge is suppressed (refusal already intentional).
    caplog.clear()
    preprocess_markdown(MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False, offline=True)
    assert "--allow-remote-images" not in caplog.text


def test_remote_image_download_gate_across_flag_combos():
    """``download_remote_images`` runs only when allowed AND not offline.

    Notes
    -----
    Spans three gates from one table so the precedence rule (offline beats
    allow) lives beside the gates it overrides:
    * ``allow_remote_images=True`` alone → downloader runs (opt-in gate);
    * no flags → downloader skipped (default-deny gate);
    * allow + ``offline=True`` → downloader skipped (kill-switch override).
    """
    # (extra kwargs to preprocess_markdown, expected downloader invocation).
    cases = [
        ({"allow_remote_images": True}, True),
        ({}, False),
        ({"allow_remote_images": True, "offline": True}, False),
    ]
    for kwargs, should_download in cases:
        with patch(
            "md2star.preprocessing.pipeline.download_remote_images",
            side_effect=lambda content, base_dir: content,
        ) as mock_dl:
            preprocess_markdown(
                MD_WITH_REMOTE_IMG,
                inject_metadata=False,
                lint_enabled=False,
                **kwargs,
            )
            # Gate: downloader invoked iff explicitly allowed and online.
            assert mock_dl.called is should_download, kwargs


def test_offline_blocks_every_lint_side_effect_even_when_lint_enabled():
    """``offline=True`` vetoes lint AND alt-text drafting despite ``--lint``.

    Notes
    -----
    Both the LLM lint pass and alt-text drafting hang off the same
    ``--lint`` switch and both leave the machine. With ``lint_enabled=True``
    the kill-switch must reach *past* the image gate and disable each of
    them; a loop asserts one gate per side-effect so a break names it.
    """
    # Every lint-triggered side-effect --offline must suppress.
    targets = [
        "md2star.preprocessing.pipeline.lint_with_llm",
        "md2star.preprocessing.pipeline.fill_empty_alt_text",
    ]
    for target in targets:
        with patch(target, side_effect=lambda *a, **k: a[0]) as mock_fn:
            preprocess_markdown(
                MD_WITH_LOCAL_IMG,
                inject_metadata=False,
                lint_enabled=True,
                offline=True,
            )
            # Offline is the hard kill-switch: this side-effect never fires.
            assert not mock_fn.called, target


# ─────────────────────────────────────────────────────────────────────
# _resolve_reference_doc — remote-template policy
# ─────────────────────────────────────────────────────────────────────


def test_reference_doc_uses_bundled_template_without_network(tmp_path):
    """Reference-doc resolution stays local when remote is opted out.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided temp dir holding a throwaway input file.

    Notes
    -----
    Folds two template gates that share an outcome, one per loop row:
    * explicit opt-out (``allow_remote_templates=False``) → bundled
      template, network untouched;
    * ``offline=True`` → bundled template, network untouched
      (kill-switch override: offline beats the v2.5.0 remote default).
    Both must return the bundled ``template.docx`` and never call urlopen.
    """
    from md2star.cache import cache_dir
    from md2star.cli import _resolve_reference_doc

    input_path = tmp_path / "foo.md"
    input_path.write_text("# hi")
    # (kwargs to _resolve_reference_doc for each no-network scenario).
    scenarios = [
        {"allow_remote_templates": False},
        {"offline": True},
    ]
    for resolve_kwargs in scenarios:
        # Wipe the XDG cache so a previously-downloaded template can't
        # short-circuit the resolver and mask the gate under test.
        for f in cache_dir("templates").glob("*"):
            f.unlink()
        # The template fetch now goes through os_helper.download_file; patch it
        # to prove it is never reached when remote is opted out / offline.
        with patch("md2star.cli.osh.download_file") as mock_dl:
            resolved = _resolve_reference_doc(
                input_path,
                "docx",
                **resolve_kwargs,
            )
            # Network must not be reached, and the bundled template wins.
            assert not mock_dl.called, resolve_kwargs
            assert resolved is not None
            assert resolved.name == "template.docx"


def test_reference_doc_downloads_when_online(tmp_path):
    """The remote template is fetched both with the explicit opt-in AND by default.

    Pins the v2.5.0 behaviour: with ``allow_remote_templates=True`` OR with no
    kwargs at all (the remote deraison.ai template is now the default branding),
    an online resolve reaches ``os_helper.download_file`` and persists the bytes.
    ``download_file`` is mocked so the test never touches the real host.
    """
    from md2star.cache import cache_dir
    from md2star.cli import _resolve_reference_doc

    input_path = tmp_path / "foo.md"
    input_path.write_text("# hi")
    fake_bytes = b"PK\x03\x04fake-docx-content"

    def _fake_download(url, file_path, **kwargs):
        # download_file streams straight to disk, so the stand-in just writes the
        # canned bytes where the resolver expects the cached template.
        Path(file_path).write_bytes(fake_bytes)

    # Both the explicit opt-in and the bare default must fetch and persist.
    for resolve_kwargs in ({"allow_remote_templates": True}, {}):
        # Wipe the cache so a prior download can't mask the fetch under test.
        for f in cache_dir("templates").glob("*"):
            f.unlink()
        with patch("md2star.cli.osh.download_file", side_effect=_fake_download) as mock_dl:
            resolved = _resolve_reference_doc(input_path, "docx", **resolve_kwargs)
            assert mock_dl.called, resolve_kwargs
            assert resolved is not None
            assert resolved.read_bytes() == fake_bytes
        assert resolved.read_bytes() == fake_bytes
