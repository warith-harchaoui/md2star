"""
md2star — minimal single-page GUI ("conversion bench") served by the API.

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`md2star.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. There is no bundler, no framework, no npm — the whole page is a
static asset the API returns verbatim.

Two GUIs, on purpose
--------------------
md2star ships two browser front-ends for two different jobs:

* **This bench** (`GET /gui` on ``md2star-api``) — a tiny drop-a-file,
  pick-a-format, download-the-result page. It aligns md2star with the rest of
  the AI Helpers suite (``audio_helper.gui`` / ``vocal_helper`` …), where every
  package's FastAPI app serves a minimal ``/gui``. It adds zero server logic:
  it POSTs to the same ``/convert`` endpoint the CLI and MCP surfaces reach.
* **The editor** (`md2star gui`, :mod:`md2star.gui_server`) — the rich,
  Overleaf-style Markdown editor with a live PDF preview, folder browser,
  template upload and draft autosave. That is the primary *human* surface and
  is unaffected by this file.

Why a separate module
---------------------
Keeping the (long) HTML out of :mod:`md2star.api` keeps the route definitions
readable and lets the rest of the suite copy this file almost verbatim: swap
the format list and the per-format form fields, keep the plumbing.

What the page does
------------------
- Drop / pick a local Markdown file (kept entirely client-side until Run).
- Choose a target format (docx / pptx / pdf) and optional metadata
  (author / language).
- POST a ``multipart/form-data`` request to the SAME ``/convert`` endpoint the
  CLI and MCP surfaces use — the GUI adds zero new server logic.
- Offer a download link for the rendered document.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

# The entire bench is this one HTML string, returned as-is by the ``/gui``
# route. Tailwind is pulled from a CDN so there is no build step; the
# JavaScript is a single inline ES module talking to the existing /convert API.
GUI_HTML: str = r"""<!doctype html>
<html lang="en" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>md2star — Conversion Bench</title>
  <!-- Tailwind via CDN: keeps the page a single self-contained file, no build. -->
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Respect users who ask for reduced motion (accessibility baseline). */
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  </style>
</head>
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  <div class="mx-auto max-w-3xl px-4 py-8">
    <header class="mb-6">
      <h1 class="text-2xl font-semibold tracking-tight">md2star — Conversion Bench</h1>
      <p class="mt-1 text-sm text-slate-600">
        Drop a Markdown file, pick a target format, convert it on the local API,
        then download the rendered document. Everything stays on this machine.
      </p>
      <p class="mt-1 text-xs text-slate-500">
        For the full editor with a live PDF preview, run <code>md2star gui</code>.
      </p>
    </header>

    <!-- 1) File input: drag-and-drop zone doubling as a file picker. -->
    <section class="mb-5">
      <label for="file" class="block text-sm font-medium mb-1">Input Markdown file</label>
      <div id="drop" tabindex="0"
           class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed
                  border-slate-300 bg-white px-4 py-8 text-center cursor-pointer
                  focus:outline-none focus:ring-2 focus:ring-blue-500 hover:border-blue-400">
        <p class="text-sm text-slate-500">Drop a .md file here, or click to choose</p>
        <p id="filename" class="mt-2 text-sm font-medium text-slate-800"></p>
        <input id="file" type="file" accept=".md,.markdown,text/markdown,text/plain" class="hidden" />
      </div>
    </section>

    <!-- 2) Target format selector. -->
    <section class="mb-5">
      <label for="fmt" class="block text-sm font-medium mb-1">Target format</label>
      <select id="fmt"
              class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="docx">docx — Word document</option>
        <option value="pptx">pptx — PowerPoint deck</option>
        <option value="pdf">pdf — PDF (needs LibreOffice on the server)</option>
      </select>
    </section>

    <!-- 3) Optional metadata fields forwarded to Pandoc. -->
    <section class="mb-5 grid grid-cols-2 gap-3">
      <div>
        <label class="block text-xs font-medium mb-1">author (optional)</label>
        <input id="author"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="block text-xs font-medium mb-1">lang (optional, e.g. en-US)</label>
        <input id="lang"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
    </section>

    <!-- 4) Run button + status line. -->
    <section class="mb-6">
      <button id="run"
              class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white
                     hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500
                     disabled:opacity-50">
        Convert
      </button>
      <span id="status" class="ml-3 text-sm text-slate-600" role="status" aria-live="polite"></span>
    </section>

    <!-- 5) Result: a download link for the rendered document. -->
    <section class="rounded-xl border border-slate-200 bg-white p-4">
      <h2 class="mb-2 text-sm font-medium">Output</h2>
      <a id="download" class="inline-block text-sm font-medium text-blue-600 hover:underline"
         hidden download>Download rendered document</a>
      <p id="out-hint" class="text-sm text-slate-500">Nothing converted yet.</p>
    </section>
  </div>

  <script type="module">
    // --- tiny DOM helpers -------------------------------------------------
    const $ = (id) => document.getElementById(id);
    const status = (msg) => { $("status").textContent = msg; };

    // Currently-selected input file (kept client-side until Convert).
    let inputFile = null;

    // --- file picker + drag-and-drop -------------------------------------
    const drop = $("drop");
    const fileInput = $("file");
    // Clicking the drop zone opens the native picker.
    drop.addEventListener("click", () => fileInput.click());
    drop.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
    });
    // Highlight while dragging over the zone.
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("border-blue-500"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("border-blue-500"));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("border-blue-500");
      if (e.dataTransfer.files.length) setInput(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => { if (fileInput.files.length) setInput(fileInput.files[0]); });

    // Register a chosen file: just show its name (Markdown is not previewable inline).
    function setInput(f) {
      inputFile = f;
      $("filename").textContent = f.name;
    }

    // --- run: POST the file to the existing /convert endpoint ------------
    $("run").addEventListener("click", async () => {
      if (!inputFile) { status("Pick a Markdown file first."); return; }
      const fmt = $("fmt").value;

      // /convert takes the file as `file` and the target format as the `fmt`
      // query param; author/lang are optional query params forwarded to Pandoc.
      const fd = new FormData();
      fd.append("file", inputFile);
      const params = new URLSearchParams({ fmt });
      if ($("author").value) params.set("author", $("author").value);
      if ($("lang").value) params.set("lang", $("lang").value);

      status("Converting…");
      $("run").disabled = true;
      $("download").hidden = true;
      try {
        const res = await fetch("/convert?" + params.toString(), { method: "POST", body: fd });
        if (!res.ok) {
          const txt = await res.text();
          status("Error " + res.status + ": " + txt.slice(0, 300));
          return;
        }
        // Binary response (the rendered document): wrap it in an object URL.
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        const stem = inputFile.name.replace(/\.[^.]+$/, "") || "document";
        const dl = $("download");
        dl.href = objUrl;
        dl.download = stem + "." + fmt;
        dl.hidden = false;
        $("out-hint").textContent = "Rendered " + stem + "." + fmt + " — click to download.";
        status("Done.");
      } catch (err) {
        status("Request failed: " + err);
      } finally {
        $("run").disabled = false;
      }
    });
  </script>
</body>
</html>
"""
