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
-- 2. AUTHOR / "EMANON" SANITISATION
--    Reads the 'author' metadata.  If the author name equals "EMANON"
--    (case-insensitive) — the project's placeholder — it is hidden.
--    Otherwise the name is kept for subtitle injection.
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
--  Author: Warith Harchaoui

-- Module-level flag: ensures only the first H1 is treated as the title.
local title_found = false

function Pandoc(doc)
    local meta = doc.meta
    local blocks = doc.blocks
    local new_blocks = {}
    local subtitle_inlines = {}
    local date_str = nil

    -- ── 1. Language / locale setup ──────────────────────────────────
    -- (Removed OS locale dependence, we handle this manually in step 3 to
    -- guarantee localization without requiring host OS package installations).

    -- ── 2. Author handling ──────────────────────────────────────────
    -- Hide the placeholder "EMANON"; keep any real author name for
    -- the subtitle line.
    if meta.author then
        local author_str = pandoc.utils.stringify(meta.author)
        if string.upper(author_str) ~= "EMANON" then
            table.insert(subtitle_inlines, pandoc.Str(author_str))
        end
        -- Remove 'author' from metadata so it does not appear twice
        meta.author = nil
    end

    -- ── 3. Date formatting ──────────────────────────────────────────
    -- Apply the strftime-style date_format to produce a localised date string.
    -- We map specific languages to manually replace %A and %B so we don't rely 
    -- on unpredictable OS 'setlocale' implementations.
    if meta.date_format then
        local fmt = pandoc.utils.stringify(meta.date_format)
        if fmt ~= "" then
            if fmt:find("%%") then
                local lang_prefix = "en"
                if meta.lang then
                    lang_prefix = pandoc.utils.stringify(meta.lang):sub(1,2):lower()
                end

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
                
                local dict = locale_dicts[lang_prefix]
                if dict then
                    local t = os.date("*t")
                    fmt = fmt:gsub("%%A", dict.days[t.wday])
                    fmt = fmt:gsub("%%B", dict.months[t.month])
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
    -- Combine author and date into "Author, Date".
    if date_str then
        if #subtitle_inlines > 0 then
            -- Separator between author and date
            table.insert(subtitle_inlines, pandoc.Str(","))
            table.insert(subtitle_inlines, pandoc.Space())
        else
            -- The date is the very first word on the line, so we 
            -- capitalize its first ASCII character (e.g. "lundi" -> "Lundi").
            local first_char = date_str:sub(1, 1)
            local rest = date_str:sub(2)
            date_str = string.upper(first_char) .. rest
        end
        table.insert(subtitle_inlines, pandoc.Str(date_str))
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
            if #subtitle_inlines > 0 then
                local subtitle_para = pandoc.Para(subtitle_inlines)
                -- Wrap in a Div with custom-style="Subtitle" so that
                -- the DOCX/PPTX reference template applies the correct
                -- font, size, and colour.
                local subtitle_div = pandoc.Div(
                    {subtitle_para},
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
