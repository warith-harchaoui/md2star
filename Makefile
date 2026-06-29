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

# Upload to PyPI. Reads credentials from `.secrets/pypi.env` (a
# gitignored file; copy `.secrets/pypi.env.example` and fill in the
# tokens). The `set -a` + `.` (source) trick exports every assignment
# in the env file so `twine` picks them up as env vars. Twine wants
# TWINE_USERNAME=__token__ + TWINE_PASSWORD=<the-pypi-token>.
publish: build
	@test -f .secrets/pypi.env || { \
		echo "Missing .secrets/pypi.env — copy .secrets/pypi.env.example and fill in your PyPI token."; \
		exit 1; \
	}
	@set -a; . ./.secrets/pypi.env; set +a; \
		twine check dist/* && twine upload dist/*

# Same machinery, but flips the credential to the TestPyPI token and
# points twine at the TestPyPI repository. Use this to rehearse the
# release without burning a real PyPI version number.
publish-testpypi: build
	@test -f .secrets/pypi.env || { \
		echo "Missing .secrets/pypi.env — copy .secrets/pypi.env.example and fill in your TestPyPI token."; \
		exit 1; \
	}
	@set -a; . ./.secrets/pypi.env; set +a; \
		if [ -z "$$TWINE_PASSWORD_TESTPYPI" ] || \
		   [ "$$TWINE_PASSWORD_TESTPYPI" = "pypi-REPLACE_ME_WITH_YOUR_TESTPYPI_TOKEN" ]; then \
			echo "TWINE_PASSWORD_TESTPYPI is unset / still the placeholder in .secrets/pypi.env."; \
			echo "Add the line, or skip publish-testpypi and use `make publish` directly."; \
			exit 1; \
		fi; \
		export TWINE_PASSWORD="$$TWINE_PASSWORD_TESTPYPI"; \
		twine check dist/* && twine upload --repository testpypi dist/*
