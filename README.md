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

</div>

A terminal UI for managing OpenVPN connections with 2FA support.

<img width="1770" height="1451" alt="README" src="https://github.com/user-attachments/assets/b28c7b47-e6d0-44e2-a63f-57d7d5675e25" />


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

## Installation

```bash
pip install vpnx
```

## Setup

```bash
# Run the interactive setup wizard
make setup
```

The setup wizard will guide you through:
1. Adding VPN configurations (name, path to .ovpn file, up script requirement)
2. Setting your username (optional - will prompt at connection if not set)
3. Configuring the password store (GPG key for secure credential storage)

## Usage

```bash
# Connect to all configured VPNs
make all

# Connect to a specific VPN
vpnx connect <vpn-name>

# List configured VPNs
make list

# Re-run setup to modify configuration
make setup
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

## Development

```bash
make test    # Run tests
make lint    # Check code style
make format  # Auto-format code
make clean   # Remove cache files
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
