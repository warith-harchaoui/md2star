# md2star Makefile
#
# Convenience targets for macOS/Linux. Run `make help` for usage.
# Windows users: use scripts/install.ps1 and scripts/uninstall.ps1 instead.
#
# Prerequisites:
#   - install: bash, python3, pip
#   - test:     Pandoc (must be on PATH)

.PHONY: install uninstall reinstall update test help

# -----------------------------------------------------------------------------
# help (default): Print available targets and usage
# -----------------------------------------------------------------------------
help:
	@echo "md2docx & md2pptx"
	@echo ""
	@echo "Targets:"
	@echo "  make install    Install into your Pandoc user directory"
	@echo "  make uninstall  Remove from your Pandoc user directory"
	@echo "  make reinstall  Uninstall then install"
	@echo "  make test       Run automated testing suite"
	@echo ""
	@echo "Docs: see README.md"

# -----------------------------------------------------------------------------
# install: Deploy md2star to ~/.pandoc and ~/.local/bin
#
# Copies Lua filters, YAML defaults, templates, metadata, and preprocessing.py.
# Installs CLI wrappers (md2docx, md2pptx).
# Ensure ~/.local/bin is on your PATH to use the commands.
# -----------------------------------------------------------------------------
install:
	@bash scripts/install.sh

# -----------------------------------------------------------------------------
# uninstall: Remove all md2star components from the system
#
# Deletes filters, defaults, templates, metadata, and CLI wrappers
# from ~/.pandoc and ~/.local/bin.
# -----------------------------------------------------------------------------
uninstall:
	@bash scripts/uninstall.sh

# -----------------------------------------------------------------------------
# reinstall: Uninstall then install
#
# Use after pulling updates to refresh deployed files with the latest changes.
# -----------------------------------------------------------------------------
reinstall: uninstall install

# -----------------------------------------------------------------------------
# update: Pull latest changes from remote Git repository and reinstall
# -----------------------------------------------------------------------------
update:
	git pull origin main
	$(MAKE) reinstall

# -----------------------------------------------------------------------------
# test: Run integration test suite
#
# Requires Pandoc installed. Exercises md2docx and md2pptx against sample
# Markdown files and verifies DOCX/PPTX output. Exit 0 if all pass.
# -----------------------------------------------------------------------------
test:
	@bash scripts/test.sh
