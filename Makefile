.PHONY: help test lint format clean install setup list all connect coverage bump-patch bump-minor bump-major _check-bump _bump-success

PYTHON := python3
SRC := vpnx

help:
	@echo "vpnx - VPN Client"
	@echo ""
	@echo "Usage:"
	@echo "  make setup          Configure VPN client (interactive wizard)"
	@echo "  make list           List configured VPNs"
	@echo "  make all            Connect to all configured VPNs"
	@echo "  make connect VPN=x  Connect to a specific VPN"
	@echo ""
	@echo "Development:"
	@echo "  make test           Run unit tests"
	@echo "  make coverage       Run tests with coverage report"
	@echo "  make lint           Check code style"
	@echo "  make format         Auto-format code"
	@echo "  make clean          Remove cache files"
	@echo "  make install        Check system dependencies"
	@echo ""
	@echo "Release:"
	@echo "  make bump-patch     Bump patch version (0.1.0 -> 0.1.1)"
	@echo "  make bump-minor     Bump minor version (0.1.0 -> 0.2.0)"
	@echo "  make bump-major     Bump major version (0.1.0 -> 1.0.0)"

test:
	@$(PYTHON) -m unittest discover -s tests -v

coverage:
	@$(PYTHON) -m pytest --cov=vpnx --cov-report=term-missing tests/

lint:
	@ruff check $(SRC) && ruff format --check $(SRC) && echo "Lint OK"

format:
	@ruff check --fix $(SRC) && ruff format $(SRC) && echo "Format OK"

clean:
	@rm -rf __pycache__ vpnx/__pycache__ tests/__pycache__
	@rm -rf vpnx/**/__pycache__
	@rm -rf .pytest_cache .coverage htmlcov
	@find . -name "*.pyc" -delete
	@echo "Cleaned"

install:
	@echo "Checking system dependencies..."
	@ok=true; \
	for cmd in openvpn gpg; do \
		if command -v $$cmd >/dev/null 2>&1; then \
			echo "  ✓ $$cmd"; \
		else \
			echo "  ✗ $$cmd (not found)"; \
			ok=false; \
		fi; \
	done; \
	echo ""; \
	if $$ok; then \
		echo "All dependencies installed"; \
	else \
		echo "Missing dependencies. Install with:"; \
		echo "  Debian/Ubuntu: sudo apt install openvpn gnupg"; \
		echo "  Fedora: sudo dnf install openvpn gnupg2"; \
		echo "  Arch: sudo pacman -S openvpn gnupg"; \
		exit 1; \
	fi

setup:
	@$(PYTHON) -m vpnx setup

list:
	@$(PYTHON) -m vpnx list

all:
	@$(PYTHON) -m vpnx all

connect:
ifndef VPN
	@echo "Usage: make connect VPN=<name>"
	@echo "Run 'make list' to see configured VPNs"
else
	@$(PYTHON) -m vpnx connect $(VPN)
endif

_check-bump:
	@command -v bump-my-version >/dev/null 2>&1 || { \
		echo "Error: bump-my-version is not installed"; \
		echo ""; \
		echo "Install it with one of:"; \
		echo "  pipx install bump-my-version"; \
		echo "  pip install --user bump-my-version"; \
		echo "  uv tool install bump-my-version"; \
		exit 1; \
	}

_bump-success:
	@NEW_TAG=$$(git describe --tags --abbrev=0); \
	echo ""; \
	echo "✓ Version bumped to $$NEW_TAG"; \
	echo ""; \
	echo "Next steps:"; \
	echo "  1. Push the commit and tag:"; \
	echo "       git push --follow-tags"; \
	echo "  2. Create a GitHub release for $$NEW_TAG:"; \
	echo "       gh release create $$NEW_TAG --generate-notes"; \
	echo "     or open: https://github.com/pirhoo/vpnx/releases/new?tag=$$NEW_TAG"

bump-patch: _check-bump
	@bump-my-version bump patch
	@$(MAKE) --no-print-directory _bump-success

bump-minor: _check-bump
	@bump-my-version bump minor
	@$(MAKE) --no-print-directory _bump-success

bump-major: _check-bump
	@bump-my-version bump major
	@$(MAKE) --no-print-directory _bump-success
