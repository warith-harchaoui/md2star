# md2star as an agent skill

`skills/md2star/` packages md2star as a **Claude Skill** *and* an **OpenCode
skill** — both ecosystems read the same `SKILL.md` (YAML frontmatter + Markdown
body + progressive-disclosure `references/`). Installing it lets an agent
discover md2star and convert Markdown to DOCX/PPTX/PDF on the user's behalf.

## Layout

```
skills/md2star/
├── SKILL.md               # name + trigger-rich description + instructions
└── references/
    ├── cli-reference.md    # full flags, template resolution, phases
    ├── surfaces.md         # CLI (argparse+click), API, MCP, GUI, minimal-gui
    └── triggers.md         # exhaustive, auditable trigger catalogue
```

## Install for Claude Code / Claude Desktop

Skills live under `~/.claude/skills/` (user) or `.claude/skills/` (project):

```bash
# user-wide
cp -r skills/md2star ~/.claude/skills/md2star
# or per-project (auto-available when working in a given repo)
mkdir -p /path/to/project/.claude/skills && cp -r skills/md2star "$_/md2star"
```

## Install for OpenCode

OpenCode reads skills from `~/.config/opencode/skills/` (or `~/.opencode/skills/`):

```bash
cp -r skills/md2star ~/.config/opencode/skills/md2star
```

## Keeping triggers enforced

The host model only sees `SKILL.md`'s `description` before deciding to load the
skill, so every capability must be named there. `scripts/check_triggers.py`
verifies the description covers every trigger bucket in `references/triggers.md`
plus a SKIP clause; it runs in CI and via `pytest tests/test_skill.py`. Edit the
description and the reference together, then re-run the checker.

## Prerequisite

The skill drives the `md2star` CLI, so the target machine needs it installed
(`pipx install md2star`, plus Pandoc; LibreOffice for PDF). The skill body tells
the agent to run `md2star doctor` first and install if missing.
