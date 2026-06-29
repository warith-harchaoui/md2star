# md2star Makefile
#
# Thin convenience layer over `pipx` (install) and `pytest` (test).
# Windows users: use scripts\install.ps1 / scripts\uninstall.ps1 instead.

.PHONY: install uninstall reinstall update test help dev build publish publish-testpypi

help:
	@echo "md2star — Markdown → DOCX/PPTX/PDF bridge"
	@echo ""
	@echo "Targets:"
	@echo "  make install    Install via pipx from the local checkout"
	@echo "  make uninstall  Remove the pipx-managed install (prompts y/N)"
	@echo "  make reinstall  uninstall + install"
	@echo "  make update     git pull + reinstall"
	@echo "  make test       Run pytest + integration suite"
	@echo "  make dev        Create .venv/ and pip install -e .[dev] (for development)"
	@echo "  make build              Build sdist + wheel into dist/ via hatch"
	@echo "  make publish-testpypi   Upload dist/* to TestPyPI (rehearsal)"
	@echo "  make publish            Upload dist/* to real PyPI"
	@echo ""
	@echo "Docs: see README.md / CONTRIBUTING.md"

install:
	@bash scripts/install.sh

uninstall:
	@bash scripts/uninstall.sh

reinstall:
	@bash scripts/uninstall.sh --yes || true
	@bash scripts/install.sh --force

update:
	git pull origin main
	$(MAKE) reinstall

test:
	@bash scripts/test.sh

# Set up a local dev venv at .venv/ with the package installed editable.
# Use this for running pytest / iterating on the code; `make install` is for
# end-users who want the CLI on their PATH.
dev:
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -e ".[dev]"
	@echo ""
	@echo "Dev venv ready. Activate with: source .venv/bin/activate"
	@echo "Run tests with: ./.venv/bin/python -m pytest tests/ -v"

# Build the sdist + wheel into dist/. Requires `hatch` (pipx install hatch).
build:
	rm -rf dist build
	hatch build

# Upload to PyPI. Credentials come from one of two gitignored files
# under .secrets/, with .pypirc preferred when present:
#
#   .secrets/.pypirc       — canonical twine config (passed via
#                            --config-file). Easiest if you already
#                            have a ~/.pypirc-style mental model.
#                            Copy .secrets/.pypirc.example to bootstrap.
#   .secrets/pypi.env      — TWINE_USERNAME + TWINE_PASSWORD env
#                            vars sourced into the shell. Useful for
#                            CI or one-shot overrides. Copy
#                            .secrets/pypi.env.example to bootstrap.
#
# Either gets you the upload; pick one. Twine wants
# TWINE_USERNAME=__token__ + TWINE_PASSWORD=<the-pypi-token>
# (the literal string `__token__` is correct — that's PyPI's
# convention for API-token auth, not a placeholder).
publish: build
	@if [ -f .secrets/.pypirc ]; then \
		twine check dist/* && twine upload --config-file .secrets/.pypirc dist/*; \
	elif [ -f .secrets/pypi.env ]; then \
		set -a; . ./.secrets/pypi.env; set +a; \
			twine check dist/* && twine upload dist/*; \
	else \
		echo "Missing credentials. Either:"; \
		echo "  - copy .secrets/.pypirc.example to .secrets/.pypirc"; \
		echo "  - or copy .secrets/pypi.env.example to .secrets/pypi.env"; \
		echo "and fill in your PyPI API token."; \
		exit 1; \
	fi

# Same machinery against TestPyPI. With .pypirc, twine reads the
# [testpypi] section directly; with pypi.env it flips
# TWINE_PASSWORD to the TestPyPI token before invoking twine.
publish-testpypi: build
	@if [ -f .secrets/.pypirc ]; then \
		twine check dist/* && twine upload --config-file .secrets/.pypirc --repository testpypi dist/*; \
	elif [ -f .secrets/pypi.env ]; then \
		set -a; . ./.secrets/pypi.env; set +a; \
			if [ -z "$$TWINE_PASSWORD_TESTPYPI" ] || \
			   [ "$$TWINE_PASSWORD_TESTPYPI" = "pypi-REPLACE_ME_WITH_YOUR_TESTPYPI_TOKEN" ]; then \
				echo "TWINE_PASSWORD_TESTPYPI is unset / still the placeholder in .secrets/pypi.env."; \
				echo "Add the line, or switch to .secrets/.pypirc which has a [testpypi] section."; \
				exit 1; \
			fi; \
			export TWINE_PASSWORD="$$TWINE_PASSWORD_TESTPYPI"; \
			twine check dist/* && twine upload --repository testpypi dist/*; \
	else \
		echo "Missing credentials. Copy .secrets/.pypirc.example or .secrets/pypi.env.example."; \
		exit 1; \
	fi
