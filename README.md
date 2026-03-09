# vpnx

<div align="center">

|      | Status |
| ---: | :--- |
| **CI checks** | [![CI](https://img.shields.io/github/actions/workflow/status/pirhoo/vpnx/ci.yml?style=flat-square)](https://github.com/pirhoo/vpnx/actions/workflows/ci.yml) |
| **Latest version** | [![PyPI](https://img.shields.io/pypi/v/vpnx?style=flat-square&color=success)](https://pypi.org/project/vpnx/) |
| **Release date** | [![Release date](https://img.shields.io/github/release-date/pirhoo/vpnx?style=flat-square&color=success)](https://github.com/pirhoo/vpnx/releases/latest) |
| **Python** | [![Python](https://img.shields.io/pypi/pyversions/vpnx?style=flat-square)](https://pypi.org/project/vpnx/) |
| **License** | [![License](https://img.shields.io/github/license/pirhoo/vpnx?style=flat-square)](https://github.com/pirhoo/vpnx/blob/main/LICENSE) |
| **Open issues** | [![Open issues](https://img.shields.io/github/issues/pirhoo/vpnx?style=flat-square&color=success)](https://github.com/pirhoo/vpnx/issues) |

A terminal UI for managing OpenVPN connections with 2FA support.

<img width="1770" alt="README" src="https://github.com/user-attachments/assets/b28c7b47-e6d0-44e2-a63f-57d7d5675e25" />

</div>

## Features

- Interactive setup wizard for configuring multiple VPNs
- Full-screen TUI with real-time connection status and bandwidth monitoring
- Secure credential storage using GPG encryption
- Support for up scripts (DNS/routing configuration)
- XDG Base Directory compliant configuration

## Requirements

- Python 3.8+
- openvpn
- gpg (for encrypted password storage)

```bash
# macOS
brew install openvpn gnupg

# Debian/Ubuntu
sudo apt install openvpn gnupg

# Fedora
sudo dnf install openvpn gnupg2

# Arch
sudo pacman -S openvpn gnupg
```

## Installation

```bash
pip install vpnx
```

## Setup

```bash
vpnx setup
```

The setup wizard will guide you through:
1. Adding VPN configurations (name, path to .ovpn file, up/down scripts)
2. Setting your username (optional - will prompt at connection if not set)
3. Configuring the password store (GPG key for secure credential storage)

## Usage

```bash
# Connect to all configured VPNs
vpnx all

# Connect to a specific VPN
vpnx connect <vpn-name>

# List configured VPNs
vpnx list
```

## Configuration

Configuration is stored in XDG-compliant directories:

```
~/.config/vpnx/
├── config.yaml        # Main configuration
└── up.sh              # Optional default up script

~/.local/share/vpnx/
├── credentials.gpg    # GPG-encrypted password
└── credentials.gpg-id # GPG key ID

~/.cache/vpnx/
└── logs/              # Connection logs
```

### config.yaml format

```yaml
username: your-username
credentials_path: ~/.local/share/vpnx/credentials
up_script: /path/to/up.sh  # Optional global up script

vpns:
  - name: PROD
    display: Production VPN
    config_path: /path/to/prod.ovpn
    needs_up_script: true
  - name: DEV
    display: Development VPN
    config_path: /path/to/dev.ovpn
    needs_up_script: false
```

## Build from source

```bash
git clone https://github.com/pirhoo/vpnx.git
cd vpnx
pip install -e ".[dev]"
```

Then use `make` targets to run the project and development tasks:

```bash
make setup          # Configure VPN client
make all            # Connect to all configured VPNs
make connect VPN=x  # Connect to a specific VPN
make list           # List configured VPNs

make test           # Run tests
make lint           # Check code style
make format         # Auto-format code
make clean          # Remove cache files
```

## Project Structure

```
├── vpnx/
│   ├── domain/          # Business logic (entities, services)
│   ├── application/     # Use cases (commands, handlers)
│   ├── infrastructure/  # External integrations (OpenVPN, GPG)
│   └── presentation/    # UI components (TUI, CLI)
└── tests/               # Unit tests
```
