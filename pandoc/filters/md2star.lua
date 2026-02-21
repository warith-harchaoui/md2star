-- md2star: Automate title extraction, author and date injection with Subtitle style, and heading ID stripping.
--
-- Logic:
-- 1. Captures the first Level 1 heading (# Title) and sets it as document title metadata.
-- 2. Checks for 'author' metadata. If it's "EMANON", it clears it.
-- 3. Handles 'date_format' and 'lang' metadata.
--    - If lang is provided (e.g., "fr-FR"), sanitizes it for Lua locale (fr_FR.UTF-8) and sets it.
--    - If format is invalid (doesn't start with %), issues a warning and skips date.
-- 4. If an author and/or date is available, injects them as a Subtitle style paragraph.
-- 5. Removes the Title heading from the body.
-- 6. Strips all other heading identifiers.

local title_found = false

function Pandoc(doc)
    local meta = doc.meta
    local blocks = doc.blocks
    local new_blocks = {}
    local author_entity = nil
    local date_str = nil

    -- Handle Language logic
    if meta.lang then
        local lang_str = pandoc.utils.stringify(meta.lang)
        if lang_str ~= "" then
            -- Sanitize lang_str for Lua os.setlocale (e.g., fr-FR -> fr_FR)
            local sanitized_lang = lang_str:gsub("-", "_")
            
            -- Attempt to set locale for time formatting
            -- We try the sanitized name, and then append .UTF-8 as fallback
            local success = os.setlocale(sanitized_lang, "time")
            if not success then
                os.setlocale(sanitized_lang .. ".UTF-8", "time")
            end
        end
    end

    -- Handle Author logic
    if meta.author then
        local author_str = pandoc.utils.stringify(meta.author)
        if author_str ~= "EMANON" then
            author_entity = meta.author
        end
    end

    -- Handle Date logic
    if meta.date_format then
        local fmt = pandoc.utils.stringify(meta.date_format)
        if fmt ~= "" then
            -- Simple check for C-style format (must contain %)
            if fmt:find("%%") then
                date_str = os.date(fmt)
            else
                io.stderr:write("[WARNING] md2star: Invalid date_format '" .. fmt .. "'. Skipping date injection.\n")
            end
        end
    end

    -- Construct subtitle content
    local subtitle_inlines = {}
    if author_entity then
        -- author_entity should be MetaInlines (a list of inlines)
        for i, val in ipairs(author_entity) do
            table.insert(subtitle_inlines, val)
        end
    end
    if date_str then
        if #subtitle_inlines > 0 then
            table.insert(subtitle_inlines, pandoc.Space())
            table.insert(subtitle_inlines, pandoc.Str("-"))
            table.insert(subtitle_inlines, pandoc.Space())
        end
        table.insert(subtitle_inlines, pandoc.Str(date_str))
    end

    for i, block in ipairs(blocks) do
        if not title_found and block.t == "Header" and block.level == 1 then
            -- Set the metadata title if not already set
            if not meta.title or #meta.title == 0 then
              meta.title = block.content
            end
            title_found = true
            
            -- Inject Subtitle (Author and/or Date)
            if #subtitle_inlines > 0 then
                local subtitle_para = pandoc.Para(subtitle_inlines)
                -- Wrap in Div for custom-style mapping to DOCX/PPTX styles
                local subtitle_div = pandoc.Div({subtitle_para}, pandoc.Attr("", {}, {["custom-style"] = "Subtitle"}))
                table.insert(new_blocks, subtitle_div)
            end
            
            -- Do not add this block (removing Title from body)
        else
            -- Process other headers to strip IDs
            if block.t == "Header" then
                block.attr.identifier = ""
            end
            table.insert(new_blocks, block)
        end
    end

    return pandoc.Pandoc(new_blocks, meta)
end
