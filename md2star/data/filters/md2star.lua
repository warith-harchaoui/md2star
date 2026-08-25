-- md2star.lua — Pandoc Lua filter for DOCX/PPTX metadata & styling.
--
-- This filter bridges the gap between Markdown semantics and Microsoft
-- Office (DOCX/PPTX) layout requirements.  It runs during the Pandoc
-- conversion pipeline and performs the following transformations:
--
-- 1. TITLE EXTRACTION
--    Captures the first Level-1 heading (# Title) and promotes it to
--    the document's 'title' metadata field if one is not already set.
--    The heading is then removed from the body to avoid duplication.
--
-- 2. AUTHOR HANDLING
--    Reads the 'author' metadata if present and keeps the name for
--    subtitle injection.  When the field is absent (the default) the
--    subtitle is built from the date alone.
--
-- 3. DATE LOCALISATION
--    Maps the BCP 47 'lang' tag (e.g. "fr-FR") to a system locale so
--    that Lua's os.date() renders month/day names in the correct
--    language.  Applies the 'date_format' metadata (strftime pattern).
--
-- 4. SUBTITLE INJECTION
--    Constructs an "Author, Date" subtitle line, wraps it in a Div
--    with custom-style="Subtitle", and inserts it right after the
--    title.  This maps to the DOCX/PPTX "Subtitle" style.
--
-- 5. HEADING-ID CLEANUP
--    Strips all automatic heading identifiers (e.g. {#my-heading}) to
--    prevent clutter in Office exports where anchors are meaningless.
--
-- 6. PAGE BREAKS (DOCX only)
--    Maps Markdown `---` (HorizontalRule) to a hard page break in DOCX
--    output. PPTX and other formats keep the default HR rendering;
--    slide structure in PPTX already comes from `## ` headings, so
--    overloading `---` there would conflict with intent.
--
--  Author: Warith Harchaoui

-- Map `---` to a DOCX page break. Other output formats keep the
-- default horizontal-rule rendering.
function HorizontalRule(el)
    if FORMAT:match("docx") then
        return pandoc.RawBlock(
            "openxml",
            '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
        )
    end
    return el
end

-- Module-level flag: ensures only the first H1 is treated as the title.
local title_found = false

function Pandoc(doc)
    local meta = doc.meta
    local blocks = doc.blocks
    local new_blocks = {}
    local subtitle_inlines = {}
    local date_str = nil

    -- ── 0. Tag every Table with a "MyTable" or "MyTableSmall" style ─
    -- Pandoc's DOCX writer maps the ``custom-style`` attribute on a Table
    -- to a named DOCX table style. Both ``MyTable`` and ``MyTableSmall``
    -- are defined in the project ``template.docx`` with thin gray borders;
    -- the latter also forces an 8 pt font + tighter cell margins so wide
    -- multi-column tables fit on the page.
    --
    -- Heuristic: switch to the small style when the table has 6 or more
    -- columns OR more than 800 total characters of cell content. Tuned
    -- against ``roitelet/docs/techreport/REPORT.md``.
    local SMALL_NCOLS = 6
    local SMALL_TOTAL_CHARS = 800

    local function table_metrics(tbl)
        local ncols = (tbl.colspecs and #tbl.colspecs) or 0
        local total = 0
        -- Pandoc 3.6 tightened pandoc.utils.stringify: it no longer accepts a
        -- ``Cell`` userdata directly, only the Blocks list inside it. Pass
        -- ``cell.contents`` so the filter works on both older and newer
        -- pandoc releases.
        local function add_row(row)
            for _, cell in ipairs(row.cells) do
                local payload = cell.contents or cell
                total = total + #pandoc.utils.stringify(payload)
            end
        end
        if tbl.head and tbl.head.rows then
            for _, row in ipairs(tbl.head.rows) do add_row(row) end
        end
        if tbl.bodies then
            for _, body in ipairs(tbl.bodies) do
                if body.body then
                    for _, row in ipairs(body.body) do add_row(row) end
                end
            end
        end
        if tbl.foot and tbl.foot.rows then
            for _, row in ipairs(tbl.foot.rows) do add_row(row) end
        end
        return ncols, total
    end

    blocks = pandoc.walk_block(pandoc.Div(blocks), {
        Table = function(t)
            local ncols, total = table_metrics(t)
            local style = (ncols >= SMALL_NCOLS or total > SMALL_TOTAL_CHARS)
                and "MyTableSmall" or "MyTable"
            t.attr = t.attr or pandoc.Attr()
            t.attr.attributes["custom-style"] = style
            return t
        end,
    }).content

    -- ── 1. Language / locale setup ──────────────────────────────────
    -- (Removed OS locale dependence, we handle this manually in step 3 to
    -- guarantee localization without requiring host OS package installations).

    -- ── 2. Author handling ──────────────────────────────────────────
    -- The GUI / CLI accepts a comma-separated list of authors, and we
    -- render it as a natural-language list:
    --     "Ada Lovelace"                           → "Ada Lovelace"
    --     "Ada Lovelace, Alan Turing"              → "Ada Lovelace and Alan Turing"
    --     "Ada, Alan, Charles Babbage"             → "Ada, Alan and Charles Babbage"
    -- The conjunction tracks the document language (lang prefix
    -- looked up below in step 3): English "and", French "et",
    -- Spanish "y", German "und", Italian / Portuguese "e",
    -- Dutch "en", Russian "и". Falls back to "and" for any other
    -- language so we never produce a missing word.
    --
    -- This same lang_prefix is also consumed by the date locale dict
    -- below; we compute it once here to avoid the duplication.
    local lang_prefix = "en"
    if meta.lang then
        lang_prefix = pandoc.utils.stringify(meta.lang):sub(1,2):lower()
    end
    local conjunction_by_lang = {
        en = "and", fr = "et", es = "y", de = "und",
        it = "e",   pt = "e",  nl = "en", ru = "и",
    }

    local function format_author_list(s)
        -- Split on commas, trim each token, drop empties.
        local items = {}
        for part in (s .. ","):gmatch("([^,]*),") do
            local t = part:gsub("^%s+", ""):gsub("%s+$", "")
            if t ~= "" then table.insert(items, t) end
        end
        if #items == 0 then return "" end
        if #items == 1 then return items[1] end
        local conj = conjunction_by_lang[lang_prefix] or "and"
        if #items == 2 then
            return items[1] .. " " .. conj .. " " .. items[2]
        end
        -- 3+: comma-join all but the last, then " <conj> <last>".
        local head = {}
        for i = 1, #items - 1 do head[i] = items[i] end
        return table.concat(head, ", ") .. " " .. conj .. " " .. items[#items]
    end

    if meta.author then
        local author_str = pandoc.utils.stringify(meta.author)
        if author_str ~= "" then
            local formatted = format_author_list(author_str)
            table.insert(subtitle_inlines, pandoc.Str(formatted))
        end
        -- Remove 'author' from metadata so it does not appear twice
        meta.author = nil
    end

    -- ── 3. Date formatting ──────────────────────────────────────────
    -- Apply the strftime-style date_format to produce a localised date string.
    -- We map specific languages to manually replace %A and %B so we don't rely
    -- on unpredictable OS 'setlocale' implementations.
    --
    -- An explicit ``date_override`` (set by the ``--date`` CLI flag or
    -- the GUI's Date field) wins outright — we use the supplied string
    -- verbatim and skip the os.date()+locale path entirely. This lets
    -- authors backdate, post-date, or stamp a non-date label
    -- ("Draft 2", "Pre-print") without fighting the auto-locale.
    if meta.date_override then
        local override_str = pandoc.utils.stringify(meta.date_override)
        if override_str ~= "" then
            date_str = override_str
        end
    elseif meta.date_format then
        local fmt = pandoc.utils.stringify(meta.date_format)
        if fmt ~= "" then
            if fmt:find("%%") then
                -- lang_prefix is computed at the top of the function
                -- (used by both the author-list formatter and the
                -- date-locale dict, so we don't recompute it here).
                local locale_dicts = {
                    ["fr"] = {
                        days = {"dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"},
                        months = {"janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"}
                    },
                    ["es"] = {
                        days = {"domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"},
                        months = {"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"}
                    },
                    ["de"] = {
                        days = {"Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"},
                        months = {"Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"}
                    },
                    ["it"] = {
                        days = {"domenica", "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato"},
                        months = {"gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"}
                    },
                    ["pt"] = {
                        days = {"domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"},
                        months = {"janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"}
                    },
                    ["nl"] = {
                        days = {"zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"},
                        months = {"januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"}
                    },
                    ["ru"] = {
                        days = {"воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"},
                        months = {"января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"}
                    }
                }
                
                local now = os.date("*t")
                -- %e (space-padded day-of-month) is a GNU strftime
                -- extension. Windows' MSVCRT strftime rejects it with
                -- "invalid conversion specifier", so we expand the
                -- value ourselves before handing the format string off
                -- to os.date.
                if fmt:find("%%e") then
                    local day_str = (now.day < 10)
                        and (" " .. now.day)
                        or tostring(now.day)
                    fmt = fmt:gsub("%%e", day_str)
                end

                local dict = locale_dicts[lang_prefix]
                if dict then
                    fmt = fmt:gsub("%%A", dict.days[now.wday])
                    fmt = fmt:gsub("%%B", dict.months[now.month])
                end

                date_str = os.date(fmt)
            else
                io.stderr:write(
                    "[WARNING] md2star: Invalid date_format '"
                    .. fmt
                    .. "'. Skipping date injection.\n"
                )
            end
        end
    end

    -- Clear any existing 'date' metadata to avoid Pandoc injecting it
    if meta.date then
        meta.date = nil
    end

    -- ── 4. Build subtitle content ───────────────────────────────────
    -- Authors and date land on TWO separate lines, each its own Para
    -- inside the Subtitle Div. The DOCX writer renders the Div as a
    -- styled paragraph group, so the user sees:
    --     Ada Lovelace, Alan Turing
    --     Sunday, June 21, 2026
    -- The split makes long author lists readable instead of running
    -- into the date with a comma. When only one of the two is
    -- present, only one line is emitted (the layout doesn't leave a
    -- blank gap).
    local subtitle_blocks = {}
    if #subtitle_inlines > 0 then
        table.insert(subtitle_blocks, pandoc.Para(subtitle_inlines))
    end
    if date_str then
        -- The date is alone on its line; capitalize the first character so
        -- localized weekdays read naturally ("lundi" → "Lundi"). For
        -- "Sunday, June…" this is a no-op.
        --
        -- Must use pandoc.text (UTF-8 codepoint aware), not the plain
        -- ``string`` library: Lua's ``string.sub``/``string.upper`` operate
        -- on raw BYTES, so on a multi-byte leading character (e.g. Russian
        -- "пятница") ``string.upper(date_str:sub(1,1))`` only ever sees the
        -- first byte of the UTF-8 sequence. In the "C" locale that byte is
        -- silently left unchanged (toupper only maps ASCII), so the day
        -- name stayed lowercase for every Russian-dated document while
        -- every other supported language capitalized correctly.
        local first_char = pandoc.text.sub(date_str, 1, 1)
        local rest = pandoc.text.sub(date_str, 2, -1)
        local capitalized = pandoc.text.upper(first_char) .. rest
        table.insert(subtitle_blocks, pandoc.Para({pandoc.Str(capitalized)}))
    end

    -- ── 5. Walk blocks: extract title, inject subtitle, strip IDs ──
    for i, block in ipairs(blocks) do
        if not title_found and block.t == "Header" and block.level == 1 then
            -- Promote the first H1 to document title metadata
            if not meta.title or #meta.title == 0 then
              meta.title = block.content
            end
            title_found = true

            -- Inject the subtitle Div immediately after the title
            if #subtitle_blocks > 0 then
                -- Wrap in a Div with custom-style="Subtitle" so the
                -- reference template's "Subtitle" paragraph style
                -- applies font, size and colour to BOTH lines.
                local subtitle_div = pandoc.Div(
                    subtitle_blocks,
                    pandoc.Attr("", {}, {["custom-style"] = "Subtitle"})
                )
                table.insert(new_blocks, subtitle_div)
            end

            -- Intentionally skip adding this H1 block (removes the
            -- redundant title from the body).
        else
            -- Strip automatic heading IDs (e.g. {#my-heading})
            if block.t == "Header" then
                block.attr.identifier = ""
            end
            table.insert(new_blocks, block)
        end
    end

    return pandoc.Pandoc(new_blocks, meta)
end
