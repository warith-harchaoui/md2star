# md2star Makefile
#
# This is a convenience for macOS/Linux users.
# Windows users can run the PowerShell scripts directly.

.PHONY: install uninstall reinstall help

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

install:
	@bash scripts/install.sh

uninstall:
	@bash scripts/uninstall.sh

reinstall: uninstall install

test:
	@bash scripts/test.sh

.PHONY: install uninstall reinstall test help
