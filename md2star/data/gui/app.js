/* md2star GUI — frontend orchestration.
 *
 * Three concerns:
 *   1. CodeMirror 6 editor (Markdown mode, live).
 *   2. PDF.js preview (re-rendered on every /render success).
 *   3. Debounced + key-bound auto-render against /render.
 *
 * Everything else (format switcher, options drawer, drag-drop, status
 * dot) is glue. No build step — ES modules loaded straight from a
 * pinned CDN URL so the file works under the stdlib http.server.
 */

// ── External dependencies (all self-hosted under /vendor/) ───────────
// CodeMirror 6 is shipped as a single esbuild bundle so all five sub-
// packages (state, view, commands, lang-markdown, language) share one
// instance — separate bundles would have incompatible EditorState
// constructors and instanceof checks would silently break the editor.
// PDF.js is the official Mozilla mjs distribution, copied verbatim.
// Refresh either via:  make vendor
// Pull the cache-bust tag the server spliced into our own <script src>
// URL, then propagate it to every vendor URL we load dynamically so the
// browser's in-memory module map cannot serve a stale codemirror.js or
// pdf.worker.min.mjs after a server restart.
const _CACHE_BUST = (() => {
  const u = new URL(import.meta.url);
  return u.searchParams.get("v") || "";
})();
const _vendor = (path) => path + (_CACHE_BUST ? `?v=${_CACHE_BUST}` : "");

// Static ES imports cannot interpolate, so the codemirror bundle path
// is plain. The server sends Cache-Control: no-store on every static
// asset; the cache-bust query string handles browsers whose module map
// would otherwise cling to an old build across server restarts.
import {
  EditorState,
  EditorView, keymap, lineNumbers, highlightActiveLine,
  defaultKeymap, indentWithTab, history, historyKeymap,
  markdown,
  syntaxHighlighting, defaultHighlightStyle,
} from "/vendor/codemirror.js";

const PDFJS_URL        = _vendor("/vendor/pdfjs/pdf.min.mjs");
const PDFJS_WORKER_URL = _vendor("/vendor/pdfjs/pdf.worker.min.mjs");

// ── Configuration constants ──────────────────────────────────────────
const AUTORENDER_DEBOUNCE_MS = 2500;   // Overleaf-style: render on pause
const ALL_PHASES = [
  "lint", "remote_images", "html_tables", "html_images", "absolutize",
  "image_assets", "language", "line_pass", "table_resize",
  "table_normalize", "image_widths", "pptx_isolation",
];
const STORAGE_KEY = "md2star.editor.draft.v1";
const DRAFT_SAVE_DEBOUNCE_MS = 4000;   // server-side persistent save

// ── DOM handles ──────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const editorMount   = $("#editor");
const previewMount  = $("#preview");
const previewEmpty  = $("#preview-empty");
const renderStatus  = $("#render-status");
const statusDot     = $("#status-dot");
const statusText    = $("#status-text");
const stderrToggle  = $("#stderr-toggle");
const stderrPanel   = $("#stderr-panel");
const optionsDrawer = $("#options-drawer");
const skipPhaseGrid = $("#skip-phase-grid");
const btnRender     = $("#btn-render");
const optTemplateDocx = $("#opt-template-file-docx");
const optTemplatePptx = $("#opt-template-file-pptx");
const optTemplateClr  = $("#opt-template-clear");
const optTemplateSt   = $("#opt-template-status");
const btnRenderLbl  = $("#btn-render-label");
const btnOptions    = $("#btn-options");
const btnTheme      = $("#btn-theme");
const btnThemeLabel = $("#btn-theme-label");
const btnOpen        = $("#btn-open");
const btnSave        = $("#btn-save");
const btnCloseFolder = $("#btn-close-folder");
const btnNewMd       = $("#btn-new-md");
const btnDeleteMd    = $("#btn-delete-md");
const sidebar        = $("#sidebar");
const sidebarRoot    = $("#sidebar-root");
const sidebarTree    = $("#sidebar-tree");
const mainGrid       = $("#main-grid");
const editorFilename = $("#editor-filename");
const formatRadios  = document.querySelectorAll('[role="radio"][data-format]');

// ── State ────────────────────────────────────────────────────────────
let selectedFormat = "pdf";  // what the Render button produces / downloads
let pendingTimer = null;     // debounce handle
let inFlight = null;         // AbortController for the active /render
let pdfjsLib = null;         // lazy-loaded PDF.js namespace

// ── PDF.js bootstrap (lazy) ──────────────────────────────────────────
async function ensurePdfJs() {
  if (pdfjsLib) return pdfjsLib;
  pdfjsLib = await import(PDFJS_URL);
  pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER_URL;
  return pdfjsLib;
}

// ── Server-side draft persistence ────────────────────────────────────
// Belt + suspenders: localStorage gives instant in-browser durability;
// POST /draft persists to $XDG_CACHE_HOME/md2star/drafts/last.md so the
// content survives browser-cache clears, machine reboots, and `md2star
// gui` restarts. The localStorage value is read first because the
// in-browser copy is the freshest source; the on-disk copy is the
// fallback when localStorage was cleared.
async function loadServerDraft() {
  try {
    const r = await fetch("/draft", { cache: "no-store" });
    if (r.status === 204 || !r.ok) return null;
    const text = await r.text();
    return text || null;
  } catch { return null; }
}

let draftSaveTimer = null;
function scheduleDraftSave(text) {
  if (draftSaveTimer) clearTimeout(draftSaveTimer);
  draftSaveTimer = setTimeout(() => {
    // When a real file is open, auto-save goes back to that file via
    // /fs/save (the user's edits feel like editing a normal document).
    // Otherwise we persist to the XDG draft cache as a generic
    // safety net.
    if (_openFilePath) {
      fetch("/fs/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: _openFilePath, content: text }),
      }).catch(() => { /* offline-tolerant */ });
    } else {
      fetch("/draft", {
        method: "POST",
        headers: { "Content-Type": "text/markdown; charset=utf-8" },
        body: text,
      }).catch(() => { /* offline-tolerant */ });
    }
  }, DRAFT_SAVE_DEBOUNCE_MS);
}
window.addEventListener("beforeunload", () => {
  // Best-effort sync save right before the tab closes so the very last
  // edit is not lost in the debounce window. Browsers cap the time we
  // can spend here, so we use sendBeacon (fire-and-forget, exempt from
  // unload timeouts). Routes to /fs/save when a real file is open,
  // /draft otherwise.
  try {
    const text = editor.state.doc.toString();
    if (_openFilePath) {
      const blob = new Blob(
        [JSON.stringify({ path: _openFilePath, content: text })],
        { type: "application/json" }
      );
      navigator.sendBeacon("/fs/save", blob);
    } else {
      navigator.sendBeacon("/draft",
        new Blob([text], { type: "text/markdown" }));
    }
  } catch { /* swallow */ }
});

// ── CodeMirror setup ────────────────────────────────────────────────
// Bootstrap content priority:
//   1. localStorage draft (freshest in-browser copy)
//   2. server-side draft from /draft (survives browser-cache clears)
//   3. bundled assets/example.md served by the server at /example
//   4. a tiny inline fallback (in case the server doesn't ship example.md)
async function loadExample() {
  try {
    const r = await fetch("/example", { cache: "no-store" });
    if (!r.ok) return null;
    return await r.text();
  } catch { return null; }
}
const _localDraft  = localStorage.getItem(STORAGE_KEY);
const _serverDraft = await loadServerDraft();
const _exampleDoc  = (_localDraft || _serverDraft) ? null : await loadExample();
const initialDoc =
  _localDraft ??
  _serverDraft ??
  _exampleDoc ??
  "# Welcome to md2star\n\n" +
  "Type Markdown on the left; the PDF preview on the right updates " +
  "automatically (~2.5 s after you stop typing) or instantly with " +
  "**⌘↵** / **Ctrl ↵**.\n";

const editor = new EditorView({
  parent: editorMount,
  state: EditorState.create({
    doc: initialDoc,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      history(),
      markdown(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      keymap.of([
        // Cmd/Ctrl+Enter renders the PDF preview right now — never
        // triggers a download, even if the format pill is set to
        // DOCX / PPTX. The dedicated Download button is the only path
        // to a binary file.
        {
          key: "Mod-Enter",
          run: () => { triggerRender(false, /*previewOnly=*/true); return true; },
        },
        // Cmd/Ctrl+S also forces a preview render (file-save muscle
        // memory, but the live auto-save already wrote to disk).
        {
          key: "Mod-s",
          preventDefault: true,
          run: () => { triggerRender(false, /*previewOnly=*/true); return true; },
        },
        ...defaultKeymap,
        ...historyKeymap,
        indentWithTab,
      ]),
      EditorView.lineWrapping,
      EditorView.theme({
        "&": { height: "100%" },
        ".cm-scroller": { fontFamily: "inherit" },
      }, { dark: false }),
      // Debounced auto-render whenever the doc changes.
      EditorView.updateListener.of((u) => {
        if (!u.docChanged) return;
        const text = u.state.doc.toString();
        localStorage.setItem(STORAGE_KEY, text);    // instant, in-browser
        scheduleDraftSave(text);                    // durable, in $XDG_CACHE_HOME
        scheduleRender();
      }),
    ],
  }),
});

// ── Skip-phase chip group ───────────────────────────────────────────
for (const phase of ALL_PHASES) {
  const label = document.createElement("label");
  label.className =
    "inline-flex cursor-pointer items-center gap-1.5 rounded-full " +
    "border border-surface-tertiary bg-surface-primary px-3 py-1 " +
    "hover:bg-surface-tertiary " +
    "dark:border-surface-tertiary-dark dark:bg-surface-primary-dark " +
    "dark:hover:bg-surface-tertiary-dark " +
    "focus-within:ring-2 focus-within:ring-brand-blue";
  label.innerHTML =
    `<input type="checkbox" value="${phase}"
            class="h-3.5 w-3.5 rounded text-brand-blue
                   focus:ring-brand-blue" />
     <span class="font-mono text-[12px]">${phase}</span>`;
  skipPhaseGrid.appendChild(label);
}

// ── Format switcher ─────────────────────────────────────────────────
function setFormat(fmt) {
  selectedFormat = fmt;
  for (const radio of formatRadios) {
    const active = radio.dataset.format === fmt;
    radio.setAttribute("aria-checked", String(active));
    radio.className = active
      ? "seg-active min-h-11 rounded-lg px-3"
      : "seg-inactive min-h-11 rounded-lg px-3";
  }
  // Uniform "Export X" label across all three formats. Click behavior:
  // every format re-paints the live PDF preview AND triggers a download
  // in the chosen format. ⌘↵ keeps the preview-only behavior so the
  // keyboard shortcut never produces an unwanted download.
  btnRenderLbl.textContent = `Export ${fmt.toUpperCase()}`;
}
formatRadios.forEach((r) => {
  r.addEventListener("click", () => setFormat(r.dataset.format));
});
setFormat("pdf");

// ── Options drawer toggle ───────────────────────────────────────────
btnOptions.addEventListener("click", () => {
  const open = !optionsDrawer.hidden;
  optionsDrawer.hidden = open;
  btnOptions.setAttribute("aria-expanded", String(!open));
});

// ── Folder browser (Open button + sidebar) ──────────────────────────
// The sidebar lists one directory level at a time. Click a folder row
// to expand/collapse; click an .md row to load it into the editor
// (subsequent auto-saves go back to that file). Non-.md files are
// shown disabled — they're visible context but ignore clicks per spec.

let _openFolderRoot = null;     // absolute path string from the server
let _openFilePath   = null;     // path relative to root, currently loaded in editor
const _expandedDirs = new Set();   // relative paths currently expanded

btnOpen.addEventListener("click", async () => {
  // Try the native picker first; if the server can't open one, prompt
  // the user for a path inline.
  try {
    const resp = await fetch("/fs/open", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!resp.ok) {
      const supplied = prompt(
        "Native folder picker unavailable. Paste an absolute folder path:"
      );
      if (!supplied) return;
      const r2 = await fetch("/fs/open", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: supplied }),
      });
      if (!r2.ok) { alert(await r2.text()); return; }
      const j2 = await r2.json();
      await _activateFolder(j2.root);
      return;
    }
    const j = await resp.json();
    await _activateFolder(j.root);
  } catch (err) {
    setStatus("error", `Open failed: ${err.message || err}`);
  }
});

btnCloseFolder.addEventListener("click", async () => {
  await fetch("/fs/close", { method: "POST" });
  _openFolderRoot = null;
  _openFilePath = null;
  _expandedDirs.clear();
  mainGrid.setAttribute("data-folder", "0");
  sidebar.classList.add("hidden");
  editorFilename.textContent = "editor.md";
});

// Save button — force the auto-save to run RIGHT NOW (the editor's
// 4 s debounce normally handles this, but the explicit Save makes
// "I'm done editing" feel concrete to the user). Writes to /fs/save
// if a real file is open; falls back to /draft (XDG cache) otherwise.
btnSave.addEventListener("click", async () => {
  const text = editor.state.doc.toString();
  if (draftSaveTimer) { clearTimeout(draftSaveTimer); draftSaveTimer = null; }
  try {
    if (_openFilePath) {
      const r = await fetch("/fs/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: _openFilePath, content: text }),
      });
      if (!r.ok) throw new Error(await r.text());
      setStatus("ok", `Saved → ${_openFilePath}`);
    } else {
      const r = await fetch("/draft", {
        method: "POST",
        headers: { "Content-Type": "text/markdown; charset=utf-8" },
        body: text,
      });
      if (!r.ok) throw new Error(await r.text());
      setStatus("ok", "Saved to draft cache.");
    }
    localStorage.setItem(STORAGE_KEY, text);
  } catch (err) {
    setStatus("error", `Save failed: ${err.message || err}`);
  }
});

btnNewMd.addEventListener("click", async () => {
  if (!_openFolderRoot) return;
  const name = prompt(
    "New file name (must end in .md):",
    `untitled-${new Date().toISOString().slice(0,10)}.md`
  );
  if (!name) return;
  const clean = name.trim().replace(/^\/+/, "");
  if (!/\.(md|markdown)$/i.test(clean)) {
    alert("Filename must end in .md or .markdown");
    return;
  }
  try {
    const resp = await fetch("/fs/create", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: clean, seed: `# ${clean.replace(/\.md$/i, "")}\n\n` }),
    });
    if (!resp.ok) { alert(await resp.text()); return; }
    await _refreshSidebar();
    await _loadFile(clean);
  } catch (err) {
    setStatus("error", `Create failed: ${err.message || err}`);
  }
});

btnDeleteMd.addEventListener("click", async () => {
  const selected = Array.from(
    sidebarTree.querySelectorAll("input[type=checkbox]:checked")
  ).map(cb => cb.value);
  if (selected.length === 0) return;
  if (!confirm(
    `Delete ${selected.length} file${selected.length > 1 ? "s" : ""}? ` +
    `This cannot be undone.`
  )) return;
  try {
    const resp = await fetch("/fs/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths: selected }),
    });
    const j = await resp.json();
    if (selected.includes(_openFilePath) && j.deleted.includes(_openFilePath)) {
      _openFilePath = null;
      editorFilename.textContent = "untitled.md";
    }
    await _refreshSidebar();
  } catch (err) {
    setStatus("error", `Delete failed: ${err.message || err}`);
  }
});

async function _activateFolder(rootPath) {
  _openFolderRoot = rootPath;
  sidebarRoot.textContent = "📁 " + rootPath.split("/").slice(-2).join("/");
  sidebarRoot.title = rootPath;
  mainGrid.setAttribute("data-folder", "1");
  sidebar.classList.remove("hidden");
  await _refreshSidebar();
}

async function _refreshSidebar() {
  if (!_openFolderRoot) return;
  // Refresh the whole tree by walking every currently-expanded dir
  // (plus the root). That keeps the existing expansion state visible
  // after a create/delete.
  sidebarTree.innerHTML = "";
  await _appendDirInto(sidebarTree, "", 0);
  _updateDeleteButtonVisibility();
}

async function _appendDirInto(parentUl, relPath, depth) {
  const url = `/fs/list?path=${encodeURIComponent(relPath)}`;
  const resp = await fetch(url);
  if (!resp.ok) return;
  const j = await resp.json();

  for (const dir of j.dirs) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "sidebar-row";
    row.style.paddingLeft = `${6 + depth * 14}px`;
    const expanded = _expandedDirs.has(dir.path);
    row.innerHTML =
      `<span class="select-none">${expanded ? "▼" : "▶"}</span>` +
      `<span class="truncate">📁 ${escapeHtml(dir.name)}</span>`;
    row.addEventListener("click", async () => {
      if (_expandedDirs.has(dir.path)) _expandedDirs.delete(dir.path);
      else _expandedDirs.add(dir.path);
      await _refreshSidebar();
    });
    li.appendChild(row);
    if (expanded) {
      const childUl = document.createElement("ul");
      li.appendChild(childUl);
      await _appendDirInto(childUl, dir.path, depth + 1);
    }
    parentUl.appendChild(li);
  }
  for (const file of j.files) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "sidebar-row" + (file.is_md ? "" : " row-disabled");
    row.style.paddingLeft = `${6 + depth * 14}px`;
    const checkbox = file.is_md
      ? `<input type="checkbox" value="${escapeAttr(file.path)}"
                onclick="event.stopPropagation()"
                class="h-3.5 w-3.5 accent-brand-blue" />`
      : `<span class="inline-block w-3.5"></span>`;
    const icon = file.is_md ? "📝" : "📄";
    const activeClass = file.path === _openFilePath ? " row-active" : "";
    row.classList.add(...activeClass.trim().split(" ").filter(Boolean));
    row.innerHTML =
      checkbox +
      `<span class="truncate">${icon} ${escapeHtml(file.name)}</span>`;
    if (file.is_md) {
      row.addEventListener("click", () => _loadFile(file.path));
    }
    li.appendChild(row);
    parentUl.appendChild(li);
  }
}

async function _loadFile(relPath) {
  try {
    const resp = await fetch(`/fs/read?path=${encodeURIComponent(relPath)}`);
    if (!resp.ok) { alert(await resp.text()); return; }
    const text = await resp.text();
    _openFilePath = relPath;
    editorFilename.textContent = "📝 " + relPath;
    replaceDoc(text);
    _refreshSidebar();   // update active highlight
  } catch (err) {
    setStatus("error", `Load failed: ${err.message || err}`);
  }
}

function _updateDeleteButtonVisibility() {
  const checked = sidebarTree.querySelectorAll(
    "input[type=checkbox]:checked"
  ).length;
  btnDeleteMd.hidden = checked === 0;
}
sidebarTree.addEventListener("change", _updateDeleteButtonVisibility);

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;",
  }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

// On page load: if the server already has a folder open (e.g. the user
// refreshed mid-session), restore the sidebar layout immediately.
fetch("/fs/status").then(r => r.json()).then(j => {
  if (j.open && j.root) _activateFolder(j.root);
}).catch(() => { /* silent */ });

editorMount.addEventListener("dragover", (e) => {
  e.preventDefault();
  editorMount.classList.add("ring-2", "ring-brand-blue");
});
editorMount.addEventListener("dragleave", () => {
  editorMount.classList.remove("ring-2", "ring-brand-blue");
});
editorMount.addEventListener("drop", async (e) => {
  e.preventDefault();
  editorMount.classList.remove("ring-2", "ring-brand-blue");
  const file = e.dataTransfer?.files?.[0];
  if (!file) return;
  if (!/\.md$/i.test(file.name) && file.type !== "text/markdown") {
    setStatus("error", `Expected a .md file, got ${file.type || file.name}`);
    return;
  }
  replaceDoc(await file.text());
});

function replaceDoc(text) {
  editor.dispatch({
    changes: { from: 0, to: editor.state.doc.length, insert: text },
  });
  localStorage.setItem(STORAGE_KEY, text);
  scheduleRender();
}

// ── Import: DOCX / PPTX / PDF → Markdown (reverse direction) ──────────
// The counterpart to Render: pick a finished document and read it back into
// the editor as Markdown via POST /extract (Kreuzberg). The picker is a hidden
// <input>; the button just triggers it, and the change handler uploads the raw
// bytes with an X-Md2star-Ext header the server uses to choose the reader.
const btnImport  = $("#btn-import");
const importFile = $("#import-file");
const btnAiLint  = $("#btn-ailint");

btnImport?.addEventListener("click", () => importFile?.click());

importFile?.addEventListener("change", async () => {
  const file = importFile.files?.[0];
  importFile.value = "";  // reset so re-picking the same file still fires
  if (!file) return;
  const ext = (file.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
  if (![".docx", ".pptx", ".pdf"].includes(ext)) {
    setStatus("error", `Import expects .docx / .pptx / .pdf, got ${file.name}`);
    return;
  }
  setStatus("busy", `Importing ${file.name}…`);
  try {
    const resp = await fetch("/extract", {
      method: "POST",
      headers: { "X-Md2star-Ext": ext, "Content-Type": "application/octet-stream" },
      body: await file.arrayBuffer(),
    });
    if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
    const j = await resp.json();
    replaceDoc(j.markdown || "");
    setStatus("ok", `Imported ${file.name} → Markdown`);
  } catch (err) {
    // A 501 here means the server lacks the optional [ocr] extra; the message
    // carries the exact `pip install 'md2star[ocr]'` hint.
    setStatus("error", `Import failed: ${err.message || err}`);
  }
});

// ── AI Lint: syntax-only repair of the buffer via POST /lint (Ollama) ─
// Mirrors the CLI --lint pass. The server never rewrites prose (repairs only)
// and returns the buffer unchanged when Ollama or the model is unavailable, so
// this button is always safe to press — worst case it reports "no change".
btnAiLint?.addEventListener("click", async () => {
  const text = editor.state.doc.toString();
  if (!text.trim()) { setStatus("error", "Nothing to lint."); return; }
  const label = btnAiLint.textContent;
  btnAiLint.disabled = true;
  btnAiLint.textContent = "Linting…";
  setStatus("busy", "AI linting the Markdown…");
  try {
    const resp = await fetch("/lint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: text }),
    });
    if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
    const j = await resp.json();
    if (j.changed) {
      replaceDoc(j.markdown || text);
      setStatus("ok", "AI lint applied syntax fixes.");
    } else {
      setStatus("ok", "AI lint: already clean (or Ollama unavailable).");
    }
  } catch (err) {
    setStatus("error", `AI lint failed: ${err.message || err}`);
  } finally {
    btnAiLint.disabled = false;
    btnAiLint.textContent = label;
  }
});

// ── Theme cycler: Light → Dark → Auto ────────────────────────────────
// Default is Auto (follows system prefers-color-scheme). The choice is
// persisted in localStorage so the next page load remembers it. We
// implement "Auto" by removing both `light` and `dark` markers and
// listening to matchMedia changes; the root .dark class is what
// Tailwind's dark: peer reacts to.
const THEME_KEY = "md2star.gui.theme.v1";
const THEME_ORDER = ["auto", "light", "dark"];
const THEME_GLYPH = { light: "🌞 Light", dark: "🌚 Dark", auto: "🌗 Auto" };

const _mql = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme(mode) {
  // Effective scheme = the mode itself, or the system preference when "auto".
  const dark = mode === "dark" || (mode === "auto" && _mql.matches);
  document.documentElement.classList.toggle("dark", dark);
  btnThemeLabel.textContent = THEME_GLYPH[mode] || THEME_GLYPH.auto;
  btnTheme.setAttribute("aria-label",
    "Theme: " + (THEME_GLYPH[mode] || THEME_GLYPH.auto) +
    " — click to cycle");
}

const _initialMode =
  THEME_ORDER.includes(localStorage.getItem(THEME_KEY))
    ? localStorage.getItem(THEME_KEY)
    : "auto";
applyTheme(_initialMode);

btnTheme.addEventListener("click", () => {
  const cur = localStorage.getItem(THEME_KEY) || "auto";
  const next = THEME_ORDER[(THEME_ORDER.indexOf(cur) + 1) % THEME_ORDER.length];
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

// Re-evaluate when the OS preference flips and we're in Auto.
_mql.addEventListener("change", () => {
  const mode = localStorage.getItem(THEME_KEY) || "auto";
  if (mode === "auto") applyTheme(mode);
});

// ── Render lifecycle ────────────────────────────────────────────────
function scheduleRender() {
  if (pendingTimer) clearTimeout(pendingTimer);
  setStatus("idle", "Edited — will render shortly…");
  pendingTimer = setTimeout(() => triggerRender(false), AUTORENDER_DEBOUNCE_MS);
}

async function triggerRender(manual, previewOnly = false) {
  if (pendingTimer) {
    clearTimeout(pendingTimer);
    pendingTimer = null;
  }
  if (inFlight) inFlight.abort();
  inFlight = new AbortController();

  const markdownSrc = editor.state.doc.toString();
  if (!markdownSrc.trim()) {
    setStatus("idle", "Empty document — nothing to render.");
    return;
  }

  setBusy(true, manual
    ? (previewOnly ? "Rendering preview…" : "Rendering…")
    : "Auto-rendering…");

  // Collect options from the drawer. ``lang`` is intentionally NOT
  // a UI knob — md2star's language phase runs langdetect on the body
  // and injects ``lang`` + ``date_format`` automatically. Documents
  // that need to override that can do so via YAML front-matter
  // (``lang: fr-FR`` at the top of the .md).
  const options = {
    author: $("#opt-author").value.trim() || undefined,
    date:   $("#opt-date").value.trim() || undefined,
    bibliography_name: $("#opt-bibname").value.trim() || undefined,
    lint: $("#opt-lint").checked,
    skip_phases: Array.from(
      skipPhaseGrid.querySelectorAll("input[type=checkbox]:checked")
    ).map((cb) => cb.value),
  };

  // For DOCX/PPTX downloads, the preview pane should keep showing the
  // most recent PDF render (so the user has visual context). We render
  // PDF first if the user picked PDF; otherwise we render two requests
  // in parallel — PDF for the preview, the chosen format for download —
  // but only fire the download one when the user is in manual mode
  // (avoids accidentally downloading files on every keystroke pause).
  const start = performance.now();
  try {
    // The PDF preview always refreshes on a click / shortcut / auto-
    // render — it is the only thing the right pane displays.
    const pdfBlob = await runRender("pdf", markdownSrc, options);
    await displayPdf(pdfBlob);

    // When the user clicked the manual "Export X" button (not the
    // preview-only ⌘↵ shortcut), trigger a browser download in the
    // chosen format. For PDF we reuse the blob we just rendered for
    // the preview — no second server round-trip. For DOCX / PPTX we
    // render a second time in the requested format.
    if (manual && !previewOnly) {
      const baseName = (_openFilePath || "md2star-output.md")
        .split("/").pop().replace(/\.(md|markdown)$/i, "");
      if (selectedFormat === "pdf") {
        triggerDownload(pdfBlob, `${baseName}.pdf`);
      } else {
        const blob = await runRender(selectedFormat, markdownSrc, options);
        triggerDownload(blob, `${baseName}.${selectedFormat}`);
      }
    }

    const ms = Math.round(performance.now() - start);
    setStatus("ok", `Rendered in ${ms} ms`);
  } catch (err) {
    if (err.name === "AbortError") return;
    setStatus("error", err.message || String(err));
  } finally {
    setBusy(false);
  }
}

async function runRender(fmt, markdownSrc, options) {
  const resp = await fetch("/render", {
    method: "POST",
    signal: inFlight.signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      format: fmt, markdown: markdownSrc, options,
    }),
  });
  // Stderr warnings live in a custom header so the body stays a clean
  // PDF/DOCX/PPTX stream we can hand straight to PDF.js / a blob URL.
  const stderr = resp.headers.get("X-Md2star-Stderr") || "";
  if (!resp.ok) {
    const body = await resp.text();
    let parsed;
    try { parsed = JSON.parse(body); } catch { parsed = { stderr: body }; }
    showStderr(parsed.stderr || body);
    throw new Error(
      `Server returned ${resp.status}. ` +
      (parsed.stderr ? "See warnings panel." : "")
    );
  }
  if (stderr) showStderr(stderr); else hideStderr();
  return await resp.blob();
}

// ── PDF rendering ────────────────────────────────────────────────────
async function displayPdf(blob) {
  const pdfjs = await ensurePdfJs();
  const buf = new Uint8Array(await blob.arrayBuffer());
  const doc = await pdfjs.getDocument({ data: buf }).promise;

  // Wipe previous canvases (but keep the empty-state placeholder so it
  // re-appears if the user clears the editor). Use Tailwind's .hidden
  // utility (display:none !important) — the placeholder carries
  // Tailwind's `grid` class which beats the browser's UA
  // `[hidden]{display:none}` rule otherwise.
  for (const el of previewMount.querySelectorAll(".pdf-page")) el.remove();
  previewEmpty.classList.add("hidden");

  // Render every page at devicePixelRatio for crispness; cap width to
  // the pane so each page fits without horizontal scrolling.
  const scale = Math.min(2, (previewMount.clientWidth - 32) / 612);  // 612pt = US Letter
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    canvas.className = "pdf-page";
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    previewMount.appendChild(canvas);
    await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  }
  renderStatus.textContent =
    doc.numPages === 1 ? "1 page" : `${doc.numPages} pages`;
}

// ── Download helper (DOCX / PPTX) ────────────────────────────────────
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
    a.remove();
  }, 1000);
}

// ── Status / stderr UI ───────────────────────────────────────────────
function setStatus(kind, text) {
  statusText.textContent = text;
  statusDot.className =
    "inline-block h-2.5 w-2.5 rounded-full status-" + (kind || "idle");
}

function setBusy(busy, label = "") {
  btnRender.disabled = busy;
  if (busy) {
    renderStatus.textContent = "rendering…";
    setStatus("busy", label);
  }
}

function showStderr(text) {
  stderrToggle.classList.remove("hidden");
  stderrPanel.textContent = text;
}
function hideStderr() {
  stderrToggle.classList.add("hidden");
  stderrPanel.hidden = true;
  stderrToggle.setAttribute("aria-expanded", "false");
}
stderrToggle.addEventListener("click", () => {
  const open = !stderrPanel.hidden;
  stderrPanel.hidden = open;
  stderrToggle.setAttribute("aria-expanded", String(!open));
});
stderrToggle.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    stderrToggle.click();
  }
});

// ── Manual render button ─────────────────────────────────────────────
btnRender.addEventListener("click", () => triggerRender(true));

// ── Custom reference template upload / clear ─────────────────────────
// Uploaded once per session via POST /template (raw .docx bytes). The
// server stores it in a process-local tempdir and uses it for every
// subsequent /render via --reference-doc, until the user hits Clear.
function _renderTemplateStatus(status) {
  // status = { docx: bool, pptx: bool }
  const parts = [];
  if (status.docx) parts.push("DOCX");
  if (status.pptx) parts.push("PPTX");
  if (parts.length === 0) {
    optTemplateSt.textContent =
      "No custom templates — using the bundled defaults.";
    optTemplateClr.hidden = true;
  } else {
    optTemplateSt.textContent =
      `Custom ${parts.join(" + ")} template${parts.length > 1 ? "s" : ""} ` +
      `active for this session.`;
    optTemplateClr.hidden = false;
  }
}

// Refresh on load so a returning user sees any leftover session state.
fetch("/template/status")
  .then(r => r.json())
  .then(j => _renderTemplateStatus(j.session_status || {}))
  .catch(() => { /* silent */ });

async function _uploadTemplate(input, fmt) {
  const file = input.files?.[0];
  if (!file) return;
  const allowedExt = fmt;   // "docx" or "pptx"
  if (!new RegExp(`\\.${allowedExt}$`, "i").test(file.name)) {
    optTemplateSt.textContent =
      `Expected a .${allowedExt} file — got ${file.name}. Upload skipped.`;
    input.value = "";
    return;
  }
  optTemplateSt.textContent = `Uploading ${file.name}…`;
  try {
    const mime = fmt === "docx"
      ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      : "application/vnd.openxmlformats-officedocument.presentationml.presentation";
    const resp = await fetch("/template", {
      method: "POST",
      headers: { "Content-Type": mime, "X-Md2star-Format": fmt },
      body: file,
    });
    if (!resp.ok) {
      const msg = await resp.text();
      optTemplateSt.textContent = `Upload failed (${resp.status}): ${msg}`;
      return;
    }
    const j = await resp.json();
    _renderTemplateStatus(j.session_status || {});
    scheduleRender();   // re-render so the new template takes effect
  } catch (err) {
    optTemplateSt.textContent = `Upload error: ${err.message || err}`;
  } finally {
    input.value = "";   // allow re-uploading the same file twice in a row
  }
}
optTemplateDocx.addEventListener(
  "change", () => _uploadTemplate(optTemplateDocx, "docx")
);
optTemplatePptx.addEventListener(
  "change", () => _uploadTemplate(optTemplatePptx, "pptx")
);

optTemplateClr.addEventListener("click", async () => {
  try {
    const resp = await fetch("/template/clear", { method: "POST" });
    const j = await resp.json().catch(() => ({}));
    _renderTemplateStatus(j.session_status || { docx: false, pptx: false });
    scheduleRender();
  } catch (err) {
    optTemplateSt.textContent = `Clear failed: ${err.message || err}`;
  }
});

// ── First render (so the welcome doc previews immediately) ───────────
scheduleRender();
