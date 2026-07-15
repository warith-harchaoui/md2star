"""Functional tests for the v1.2.0 offline / remote-resource security policy.

The contract these tests defend:

* By default md2star does NOT reach the network. Remote images are left
  in place and a warning points at the opt-in flag.
* ``--allow-remote-images`` opts in to ``download_remote_images``.
* ``--allow-remote-templates`` opts in to the deraison.ai reference-doc
  fallback in ``_resolve_reference_doc``.
* ``--offline`` is the hard kill-switch: it forces every network / LLM
  side-effect off (images, templates, lint, alt-text) and silences the
  soft-refuse warning — even when the ``allow_*`` flags are also present.

Each *security gate* keeps its own test so a regression names the exact
gate it broke. Value-families (allowed vs. default, etc.) are folded as
in-body loops rather than dropped. Assertions run at the API level
(``preprocess_markdown`` + ``_resolve_reference_doc``) so they're
independent of the CLI's argparse layer.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

from md2star.preprocessing import preprocess_markdown

MD_WITH_REMOTE_IMG = (
    "Some prose.\n\n"
    "![hero](https://example.invalid/banner.png)\n\n"
    "More prose.\n"
)
MD_WITH_LOCAL_IMG = (
    "Some prose.\n\n"
    "![local](./images/foo.png)\n\n"
    "More prose.\n"
)


# ─────────────────────────────────────────────────────────────────────
# preprocess_markdown — remote-image policy
# ─────────────────────────────────────────────────────────────────────


def test_default_deny_leaves_remote_image_and_warns_at_opt_in_flag(caplog):
    """Default: the remote URL is untouched and a warning names the opt-in.

    Notes
    -----
    Covers two facets of the *default-deny* gate in one realistic run:
    (1) no network happened, so the URL survives verbatim for pandoc to
    see; (2) the soft-refuse warning flows through the ``md2star`` logger
    and tells the user both *which* URL was skipped and *how* to allow it.
    """
    caplog.set_level(logging.WARNING, logger="md2star")
    result = preprocess_markdown(
        MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False,
    )
    # No download was permitted → the URL is preserved exactly as written.
    assert "https://example.invalid/banner.png" in result
    # The warning must be actionable: name the URL and the opt-in flag.
    assert "--allow-remote-images" in caplog.text
    assert "https://example.invalid/banner.png" in caplog.text


def test_no_remote_image_produces_no_skip_warning(caplog):
    """A document with only local images logs no remote-skip warning.

    Notes
    -----
    Guards the warning against false positives: the soft-refuse surface
    must stay silent when there is nothing remote to refuse.
    """
    caplog.set_level(logging.WARNING, logger="md2star")
    preprocess_markdown(
        MD_WITH_LOCAL_IMG, inject_metadata=False, lint_enabled=False,
    )
    # Nothing remote → the opt-in hint must not appear in the log.
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
                inject_metadata=False, lint_enabled=False,
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


def test_offline_silences_the_remote_image_warning(caplog):
    """In offline mode the soft-refuse warning is suppressed as noise.

    Notes
    -----
    The default-deny warning exists to nudge users toward the opt-in flag.
    Once the user has declared ``--offline`` the refusal is explicit and
    intentional, so re-emitting the nudge would be pure noise — it must be
    silenced.
    """
    caplog.set_level(logging.WARNING, logger="md2star")
    preprocess_markdown(
        MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False,
        offline=True,
    )
    # Explicit --offline → no soft-refuse hint should be logged.
    assert "--allow-remote-images" not in caplog.text


# ─────────────────────────────────────────────────────────────────────
# _resolve_reference_doc — remote-template policy
# ─────────────────────────────────────────────────────────────────────


def test_reference_doc_uses_bundled_template_without_network(tmp_path):
    """Reference-doc resolution stays local unless remote is explicitly on.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided temp dir holding a throwaway input file.

    Notes
    -----
    Folds two template gates that share an outcome, one per loop row:
    * default (no ``allow_remote_templates``) → bundled template, network
      untouched (default-deny gate);
    * allow + ``offline=True`` → bundled template, network untouched
      (kill-switch override: offline beats allow).
    Both must return the bundled ``template.docx`` and never call urlopen.
    """
    from md2star.cache import cache_dir
    from md2star.cli import _resolve_reference_doc

    input_path = tmp_path / "foo.md"
    input_path.write_text("# hi")
    # (kwargs to _resolve_reference_doc for each no-network scenario).
    scenarios = [
        {},
        {"allow_remote_templates": True, "offline": True},
    ]
    for resolve_kwargs in scenarios:
        # Wipe the XDG cache so a previously-downloaded template can't
        # short-circuit the resolver and mask the gate under test.
        for f in cache_dir("templates").glob("*"):
            f.unlink()
        with patch("urllib.request.urlopen") as mock_urlopen:
            resolved = _resolve_reference_doc(
                input_path, "docx", **resolve_kwargs,
            )
            # Network must not be reached, and the bundled template wins.
            assert not mock_urlopen.called, resolve_kwargs
            assert resolved is not None
            assert resolved.name == "template.docx"


def test_reference_doc_downloads_when_remote_explicitly_allowed(tmp_path):
    """``allow_remote_templates=True`` (and online) fetches the remote doc.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided temp dir holding a throwaway input file.

    Notes
    -----
    The positive half of the template gate: with the opt-in flag set and
    no ``--offline``, ``urlopen`` is called and its bytes are written to
    the resolved reference doc. ``urlopen`` is mocked so the test never
    touches the real network.
    """
    from md2star.cache import cache_dir
    from md2star.cli import _resolve_reference_doc

    input_path = tmp_path / "foo.md"
    input_path.write_text("# hi")
    for f in cache_dir("templates").glob("*"):
        f.unlink()

    fake_bytes = b"PK\x03\x04fake-docx-content"

    class _FakeResp:
        """Minimal context-manager stand-in for a urlopen response."""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            """Return the canned docx bytes the resolver should persist."""
            return fake_bytes

    with patch(
        "urllib.request.urlopen", return_value=_FakeResp(),
    ) as mock_urlopen:
        resolved = _resolve_reference_doc(
            input_path, "docx",
            allow_remote_templates=True,
        )
        # Opt-in + online → network fetched and its bytes were persisted.
        assert mock_urlopen.called
        assert resolved is not None
        assert resolved.read_bytes() == fake_bytes
