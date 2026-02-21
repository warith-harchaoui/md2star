# md2star Makefile
#
# This is a convenience for macOS/Linux users.
# Windows users can run the PowerShell scripts directly.

.PHONY: install uninstall reinstall help

help:
	@echo "md2star"
	@echo ""
	@echo "Targets:"
	@echo "  make install    Install md2star into your Pandoc user directory"
	@echo "  make uninstall  Remove md2star from your Pandoc user directory"
	@echo "  make reinstall  Uninstall then install"
	@echo ""
	@echo "Docs: see README.md"

install:
	@bash scripts/install.sh

uninstall:
	@bash scripts/uninstall.sh

reinstall: uninstall install
