.PHONY: help test lint format clean install setup list all

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
	@echo "  make setup    Configure VPN client"
	@echo "  make list     List configured VPNs"
	@echo "  make all      Connect to all configured VPNs"

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

setup:
	@$(PYTHON) run.py setup

list:
	@$(PYTHON) run.py list

all:
	@$(PYTHON) run.py all
