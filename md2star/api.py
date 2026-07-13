"""
md2star — FastAPI HTTP surface.

Exposes the md2star Markdown → DOCX / PPTX / PDF bridge as HTTP endpoints so it
can sit behind any reverse proxy and be consumed by other services. Kept
intentionally aligned with the rest of the toolkit's suite (``os_helper.api`` /
``vocal_helper.api`` / …): a liveness probe, a JSON environment diagnostic, and
a multipart **action** that uploads Markdown and streams back the compiled
document.

Exposed surface:

- ``GET  /health`` — liveness probe.
- ``GET  /doctor`` — the same environment diagnostic as ``md2star doctor
  --json`` (which tools are present, per-format feature status).
- ``POST /convert`` — upload a ``.md`` file, pick a target format
  (``docx`` / ``pptx`` / ``pdf``), and stream back the rendered document.

Install the extra to get the runtime dependencies::

    pip install 'md2star[api]'

Then run the app with any ASGI server::

    uvicorn md2star.api:app --host 0.0.0.0 --port 8000
    # or: md2star-api      (see [project.scripts])

Note that conversion still requires Pandoc on the host (and LibreOffice for PDF);
``GET /doctor`` reports what is available, and ``POST /convert`` returns HTTP 503
when a required system tool is missing.

Usage Example
-------------
>>> # Start the server:
>>> #   uvicorn md2star.api:app --reload
>>> # Convert Markdown to DOCX:
>>> #   curl -F 'file=@notes.md' 'http://localhost:8000/convert?fmt=docx' -o notes.docx
>>> # Environment diagnostic:
>>> #   curl -s http://localhost:8000/doctor
>>> # Full OpenAPI docs at http://localhost:8000/docs

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

# FastAPI is an OPTIONAL dependency (the ``[api]`` extra). Importing this
# module without it should fail with an actionable install hint rather than a
# bare ModuleNotFoundError, so we re-raise with the exact pip command.
try:
    from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
    from fastapi.responses import FileResponse
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'md2star[api]'"
    ) from exc

from . import __version__
from .cli import _convert
from .doctor import run_checks
from .errors import (
    InvalidInputError,
    Md2starError,
    MissingDependencyError,
)

app = FastAPI(
    title="md2star",
    version=__version__,
    description=(
        "Markdown → DOCX / PPTX / PDF via Pandoc, with curated styling. "
        "HTTP surface: health, environment doctor, and a convert action."
    ),
)

# Target formats and the MIME type each compiled document is streamed with.
_FORMAT_MEDIA: dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe.

    Returns
    -------
    dict of str
        ``{"status": "ok"}`` when the service is up.
    """
    return {"status": "ok"}


@app.get("/doctor")
def doctor() -> dict:
    """Report the environment md2star runs in (tools present, feature status).

    Returns
    -------
    dict
        The same payload as ``md2star doctor --json``: a list of ``checks``, a
        per-format ``features`` map, and a ``core_failing`` flag.
    """
    # Reuse the exact same check engine as the CLI's ``doctor`` so the HTTP and
    # terminal diagnostics never drift apart; we only reshape it into JSON.
    report = run_checks()
    return {
        # Flatten each Check dataclass into a plain dict for the JSON response.
        "checks": [
            {"name": c.name, "status": c.status, "detail": c.detail, "section": c.section}
            for c in report.checks
        ],
        # Per-format readiness (can we actually produce docx/pptx/pdf/mermaid?).
        "features": {
            fmt: report.feature_status(fmt) for fmt in ("docx", "pptx", "pdf", "mermaid")
        },
        # True when a core tool is missing — a quick top-level red/green flag.
        "core_failing": report.core_failing(),
    }


@app.post("/convert", response_model=None)
async def convert(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="The input Markdown (.md) file."),
    fmt: str = Query("docx", description="Target format: docx, pptx or pdf."),
    author: str | None = Query(None, description="Document author (Pandoc metadata)."),
    lang: str | None = Query(None, description="Document language (BCP 47, e.g. en-US)."),
    date: str | None = Query(None, description="Override the auto-generated date string."),
) -> FileResponse:
    """Convert an uploaded Markdown file into a rendered document and stream it.

    Parameters
    ----------
    background : fastapi.BackgroundTasks
        Used to delete the temp working directory after the response streams.
    file : fastapi.UploadFile
        The input Markdown document.
    fmt : str, optional
        Target format — one of ``docx`` / ``pptx`` / ``pdf``. Defaults to ``docx``.
    author, lang, date : str or None, optional
        Optional Pandoc metadata forwarded to the converter when provided.

    Returns
    -------
    fastapi.responses.FileResponse
        The compiled document, streamed with the format's MIME type.

    Raises
    ------
    fastapi.HTTPException
        400 for an unknown format or invalid Markdown input, 503 when a required
        system tool (Pandoc / LibreOffice) is missing, 500 on any other
        conversion failure.
    """
    # Normalise + validate the target format up front so a typo fails fast with
    # a 400 rather than deep inside the converter.
    fmt = fmt.lower()
    if fmt not in _FORMAT_MEDIA:
        raise HTTPException(
            status_code=400,
            detail=f"fmt must be one of {sorted(_FORMAT_MEDIA)}; got {fmt!r}",
        )

    # One temp dir per request holds the upload + the rendered output. We
    # register its cleanup as a background task so it runs AFTER FileResponse
    # has finished streaming — deleting it earlier would truncate the download.
    work = tempfile.mkdtemp(prefix="md2star_api_")
    background.add_task(shutil.rmtree, work, ignore_errors=True)

    # md2star's converter is path-in / path-out; stage the upload on disk and
    # give it an explicit output path so we know exactly what to stream back.
    # Derive a safe stem from the upload name (falling back to "document" when
    # the client sends no/empty filename) and reuse it for both the staged
    # input and the output, so the download keeps a sensible name.
    stem = Path(file.filename or "document").stem or "document"
    in_path = os.path.join(work, f"{stem}.md")
    out_path = os.path.join(work, f"{stem}.{fmt}")
    with open(in_path, "wb") as f:
        f.write(await file.read())

    # Translate the optional query params into the same CLI flags the converter
    # already understands — only appending a flag when the caller supplied it.
    argv = [in_path, "-o", out_path]
    for flag, value in (("--author", author), ("--lang", lang), ("--date", date)):
        if value:
            argv += [flag, value]

    try:
        _convert(fmt, argv)
    except MissingDependencyError as exc:
        # A required system tool (Pandoc / LibreOffice) is absent — this is an
        # environment problem, not a bad request; 503 tells the caller to retry
        # against a properly provisioned host.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Md2starError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not os.path.exists(out_path):  # pragma: no cover — defensive
        raise HTTPException(status_code=500, detail="conversion produced no output file")

    return FileResponse(
        out_path, media_type=_FORMAT_MEDIA[fmt], filename=os.path.basename(out_path)
    )


def main() -> None:
    """Entry point for the ``md2star-api`` console script.

    Boots the FastAPI app with ``uvicorn`` in single-worker mode. Meant for
    local / container usage; behind a real load balancer, run ``uvicorn`` /
    ``gunicorn`` directly against :data:`md2star.api.app`.
    """
    import uvicorn

    # Host/port are env-overridable so the same image runs unchanged across
    # environments (0.0.0.0 to be reachable from outside a container).
    host = os.environ.get("MD2STAR_HOST", "0.0.0.0")
    port = int(os.environ.get("MD2STAR_PORT", "8000"))
    # Single worker: conversions shell out to Pandoc/LibreOffice, so scale by
    # running several processes behind a load balancer, not in-process workers.
    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":  # pragma: no cover
    main()
