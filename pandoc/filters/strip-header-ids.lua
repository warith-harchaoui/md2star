-- md2star: Remove heading identifiers so Pandoc doesn't emit DOCX bookmarks for headings.
--
-- Why this exists:
--   When converting Markdown -> DOCX, Pandoc can embed per-heading anchors (identifiers).
--   In DOCX these can become Word bookmarks. When the DOCX is converted to Google Docs,
--   Google Docs may display a small "bookmark" marker icon next to headings.
--
-- What this filter does:
--   For every heading, it clears the identifier (anchor). This prevents Pandoc from
--   emitting bookmark targets for headings in the produced DOCX.
--
-- Trade-off:
--   If your Markdown uses internal links to headings (e.g. [Jump](#my-heading)),
--   those links won't have targets anymore.
function Header(h)
  h.attr.identifier = ""
  return h
end
