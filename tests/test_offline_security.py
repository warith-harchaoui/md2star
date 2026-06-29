"""Tests for the v1.2.0 offline / remote-resource security policy.

The contract:

* By default, md2star does NOT reach the network.
* ``--allow-remote-images`` opts in to ``download_remote_images``.
* ``--allow-remote-templates`` opts in to the deraison.ai template
  fallback in ``_resolve_reference_doc``.
* ``--offline`` forces both off (and silences the lint pass) even
  when the opt-in flags are also present.

These tests assert the behaviour at the API level (``preprocess_markdown``
+ ``_resolve_reference_doc``) so they're independent of the CLI's
argparse layer.
"""

from __future__ import annotations

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


class TestRemoteImagesDefaultDeny:
    """By default, remote images are NOT downloaded and a warning fires."""

    def test_remote_image_is_left_in_place(self, capsys):
        result = preprocess_markdown(
            MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False,
        )
        # The URL is preserved verbatim — pandoc will see it as a
        # remote ref. (DOCX writers drop it, but that's the honest
        # consequence of "no network was permitted".)
        assert "https://example.invalid/banner.png" in result

    def test_warning_mentions_the_opt_in_flag(self, capsys):
        preprocess_markdown(
            MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False,
        )
        stderr = capsys.readouterr().err
        assert "--allow-remote-images" in stderr
        assert "https://example.invalid/banner.png" in stderr

    def test_no_warning_when_no_remote_images(self, capsys):
        preprocess_markdown(
            MD_WITH_LOCAL_IMG, inject_metadata=False, lint_enabled=False,
        )
        stderr = capsys.readouterr().err
        assert "--allow-remote-images" not in stderr


class TestRemoteImagesOptIn:
    """``allow_remote_images=True`` lets the download phase run."""

    def test_download_called_when_allowed(self):
        # Patch download_remote_images to confirm it's invoked. We
        # don't care about its return value — the test is just that
        # the gating works.
        with patch(
            "md2star.preprocessing.pipeline.download_remote_images",
            side_effect=lambda content, base_dir: content,
        ) as mock_dl:
            preprocess_markdown(
                MD_WITH_REMOTE_IMG,
                inject_metadata=False, lint_enabled=False,
                allow_remote_images=True,
            )
            assert mock_dl.called

    def test_download_not_called_by_default(self):
        with patch(
            "md2star.preprocessing.pipeline.download_remote_images",
            side_effect=lambda content, base_dir: content,
        ) as mock_dl:
            preprocess_markdown(
                MD_WITH_REMOTE_IMG,
                inject_metadata=False, lint_enabled=False,
            )
            assert not mock_dl.called


class TestOfflineMode:
    """``offline=True`` is the hard kill-switch — even allow_* is ignored."""

    def test_offline_blocks_remote_images_even_when_allowed(self):
        with patch(
            "md2star.preprocessing.pipeline.download_remote_images",
            side_effect=lambda content, base_dir: content,
        ) as mock_dl:
            preprocess_markdown(
                MD_WITH_REMOTE_IMG,
                inject_metadata=False, lint_enabled=False,
                allow_remote_images=True,
                offline=True,
            )
            assert not mock_dl.called

    def test_offline_blocks_lint_even_when_enabled(self):
        with patch(
            "md2star.preprocessing.pipeline.lint_with_llm",
            side_effect=lambda content: content,
        ) as mock_lint:
            preprocess_markdown(
                MD_WITH_LOCAL_IMG,
                inject_metadata=False,
                lint_enabled=True,
                offline=True,
            )
            assert not mock_lint.called

    def test_offline_blocks_alt_text_drafting_even_when_lint_enabled(self):
        """Alt-text drafting piggy-backs on ``--lint`` — ``--offline`` blocks it."""
        with patch(
            "md2star.preprocessing.pipeline.fill_empty_alt_text",
            side_effect=lambda content, base_dir: content,
        ) as mock_alt:
            preprocess_markdown(
                MD_WITH_LOCAL_IMG,
                inject_metadata=False,
                lint_enabled=True,
                offline=True,
            )
            assert not mock_alt.called

    def test_offline_silences_remote_image_warning(self, capsys):
        # The warning is the "soft refuse" surface; in offline mode the
        # refusal is explicit and the warning is noise.
        preprocess_markdown(
            MD_WITH_REMOTE_IMG, inject_metadata=False, lint_enabled=False,
            offline=True,
        )
        # We still don't download AND we don't print the warning
        # (because the user already declared --offline; they know).
        assert "--allow-remote-images" not in capsys.readouterr().err


# ─────────────────────────────────────────────────────────────────────
# _resolve_reference_doc — remote-template policy
# ─────────────────────────────────────────────────────────────────────


class TestResolveReferenceDoc:
    """The deraison.ai template fallback is gated behind --allow-remote-templates."""

    def test_falls_back_to_bundled_when_remote_not_allowed(self, tmp_path):
        from md2star.cli import _resolve_reference_doc
        input_path = tmp_path / "foo.md"
        input_path.write_text("# hi")
        # Wipe the XDG cache so we're sure no previously-downloaded
        # template short-circuits the test.
        from md2star.cache import cache_dir
        for f in cache_dir("templates").glob("*"):
            f.unlink()
        with patch("urllib.request.urlopen") as mock_urlopen:
            resolved = _resolve_reference_doc(input_path, "docx")
            # The bundled template should be returned; urlopen never called.
            assert resolved is not None
            assert resolved.name == "template.docx"
            assert not mock_urlopen.called

    def test_downloads_when_explicitly_allowed(self, tmp_path):
        from md2star.cache import cache_dir
        from md2star.cli import _resolve_reference_doc
        input_path = tmp_path / "foo.md"
        input_path.write_text("# hi")
        for f in cache_dir("templates").glob("*"):
            f.unlink()
        # Mock the urlopen response so the test doesn't actually hit
        # the network.
        fake_bytes = b"PK\x03\x04fake-docx-content"
        class _FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return fake_bytes
        with patch("urllib.request.urlopen", return_value=_FakeResp()) as mock_urlopen:
            resolved = _resolve_reference_doc(
                input_path, "docx",
                allow_remote_templates=True,
            )
            assert mock_urlopen.called
            assert resolved is not None
            assert resolved.read_bytes() == fake_bytes

    def test_offline_blocks_download_even_when_allowed(self, tmp_path):
        from md2star.cache import cache_dir
        from md2star.cli import _resolve_reference_doc
        input_path = tmp_path / "foo.md"
        input_path.write_text("# hi")
        for f in cache_dir("templates").glob("*"):
            f.unlink()
        with patch("urllib.request.urlopen") as mock_urlopen:
            resolved = _resolve_reference_doc(
                input_path, "docx",
                allow_remote_templates=True,
                offline=True,
            )
            assert not mock_urlopen.called
            assert resolved is not None
            # Bundled fallback wins.
            assert resolved.name == "template.docx"
