# Aegon Trading Bot

A Python-based trading bot for Lighter with risk management, portfolio tracking, and copy trading capabilities.

## Quick Start

1. **Clone and setup:**
   ```bash
   git clone <repo-url>
   cd aegon
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   ```bash
   # Copy example configs and edit with your real credentials
   cp configs/.env.testnet.example configs/.env.testnet
   cp configs/.env.mainnet.example configs/.env.mainnet
   
   # Edit the files with your actual Lighter credentials
   nano configs/.env.testnet
   ```

3. **Test the setup:**
   ```bash
   # Check account info
   python apps/trader/main.py --network testnet account
   
   # List open orders
   python apps/trader/main.py --network testnet open-orders
   ```

## Configuration

### Environment Files

- **`configs/.env.testnet`** - Testnet configuration (create from `.env.testnet.example`)
- **`configs/.env.mainnet`** - Mainnet configuration (create from `.env.mainnet.example`)

**Required credentials:**
- `ACCOUNT_INDEX` - Your Lighter account index
- `API_KEY_INDEX` - Your API key index (2-254)
- `ETH_PRIVATE_KEY` - Your Ethereum private key
- `API_KEY_PRIVATE_KEY` - Your Lighter API private key

### Security

⚠️ **Never commit real credentials to git!** The `.gitignore` file excludes sensitive config files. Only the `.example` files are tracked in version control.

## CLI Commands

### Account Management
```bash
# View account balances and positions
python apps/trader/main.py --network testnet account

# View raw JSON data
python apps/trader/main.py --network testnet account --json
```

### Order Management
```bash
# List open orders
python apps/trader/main.py --network testnet open-orders

# Place a bracket order
python apps/trader/main.py --network mainnet place \
  --market BTC --side BUY --size 2 \
  --stop 20.0 --tp 25.0 --lev 2.0

# Close a position
python apps/trader/main.py --network testnet close \
  --market HYPE-USDC --current-side BUY --size 10
```

## Project Structure

```
aegon/
├── apps/                    # Applications
│   ├── trader/             # CLI trading interface
│   ├── api/                # REST API server
│   └── backtester/         # Backtesting engine
├── packages/               # Core packages
│   ├── lighter_sdk_adapter/ # Lighter API integration
│   ├── core/               # Core models and use cases
│   ├── risk/               # Risk management
│   ├── execution/          # Order execution
│   ├── portfolio/          # Portfolio tracking
│   ├── signals/            # Signal processing
│   └── followers/          # Copy trading
├── configs/                # Configuration files
└── tests/                  # Test suites
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
python -m pytest tests/

# Run linting
flake8 packages/ apps/
```

## License

MIT License - see LICENSE file for details.
