.PHONY: help test lint format clean install run setup list ext int both

PYTHON := python3
SRC := $(shell find lib -name "*.py") run.py
TESTS := $(shell find tests -name "test_*.py")

help:
	@echo "VPN Client - Available targets:"
	@echo "  make test     Run unit tests"
	@echo "  make lint     Check code style"
	@echo "  make clean    Remove cache files"
	@echo "  make install  Install dependencies (none required)"
	@echo ""
	@echo "VPN Commands:"
	@echo "  make setup    Configure credentials"
	@echo "  make list     List available VPNs"
	@echo "  make ext      Connect to EXT VPN"
	@echo "  make int      Connect to INT VPN"
	@echo "  make both     Connect to both VPNs"

test:
	@cd lib && $(PYTHON) -m unittest discover -s ../tests -v

lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check $(SRC) && ruff format --check $(SRC) && echo "Lint OK"; \
	else \
		$(PYTHON) -m py_compile $(SRC) && echo "Syntax OK"; \
	fi

format:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check --fix $(SRC) && ruff format $(SRC) && echo "Format OK"; \
	else \
		echo "ruff not installed"; \
	fi

clean:
	@rm -rf __pycache__ lib/__pycache__ tests/__pycache__
	@rm -rf .pytest_cache
	@find . -name "*.pyc" -delete
	@echo "Cleaned"

install:
	@echo "No Python dependencies required (stdlib only)"
	@echo "System dependencies: openvpn pass gpg"

run:
	@$(PYTHON) run.py both

setup:
	@$(PYTHON) run.py setup

list:
	@$(PYTHON) run.py list

ext:
	@$(PYTHON) run.py ext

int:
	@$(PYTHON) run.py int

both:
	@$(PYTHON) run.py both
