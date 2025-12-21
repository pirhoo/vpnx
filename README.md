# VPN Client

A terminal UI for connecting to ICIJ VPNs.

## Requirements

- Python 3.8+
- openvpn
- pass (password manager)
- gpg

## Setup

```bash
# First time setup
make setup
```

This will prompt for your GPG key ID and ICIJ credentials.

## Usage

```bash
# Connect to both VPNs (recommended)
make both

# Or connect to a single VPN
make ext
make int

# List available VPNs
make list
```

## Development

```bash
make test    # Run tests
make lint    # Check code style
make format  # Auto-format code
```

## Project Structure

```
├── lib/
│   ├── domain/          # Business logic
│   ├── application/     # Use cases
│   ├── infrastructure/  # External integrations
│   └── presentation/    # UI components
├── tests/               # Unit tests
├── certificates/        # VPN config files
├── credentials/         # Password store
└── scripts/             # Helper scripts
```
