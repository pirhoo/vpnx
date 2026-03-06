.PHONY: help test lint format clean install setup list all connect coverage

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
