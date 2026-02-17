# Polymarket Bot: Automated Trading & Arbitrage System

An advanced Python trading bot for Polymarket prediction markets. This system provides high-performance automation, including gasless trading, real-time WebSocket market data, and sophisticated arbitrage and volatility strategies. Designed for efficient capital allocation, low-latency execution, and scalable quantitative crypto trading in active and high-frequency environments.

**Status:** Live trading enabled. Dashboard available at your configured domain.

_Read the [Medium article](https://medium.com/@benjamin.bigdev/high-roi-polymarket-arbitrage-in-2026-programmatic-dutch-book-strategies-bots-and-portfolio-41372221bb79) for more insight._

---

## Table of Contents
1. [Contact](#contact)
2. [Demo Video](#demo-video)
3. [Strategy Overview](#strategy-overview)
    - [Directional/Speculative Strategy](#directionalspeculative-strategy)
    - [Pure Arbitrage](#pure-arbitrage)
4. [Status](#status)
5. [Features](#features)
6. [Setup](#setup)
7. [Configuration](#configuration)
8. [Contract Approvals](#contract-approvals)
9. [Geo-Restrictions & Proxy Setup](#geo-restrictions--proxy-setup)
10. [Documentation](#documentation)
11. [License](#license)

---

## Contact

- Telegram: [@BenjaminCup](https://t.me/BenjaminCup)

---

## Demo Video

https://github.com/user-attachments/assets/f06d66ee-4408-4076-91c3-5476d780cf7a

---

## Strategy Overview

### Directional/Speculative Strategy (Binary Yes/No Markets)
1. **Formulate a Directional Conviction:** Identify if "Yes" or "No" is undervalued.
2. **Initiate Position:** Buy the favored outcome when near $0.60. In thin books, this moves the price to ~$0.61–$0.62.
3. **Market Impact:** Others interpret this as strong conviction; retail/FOMO may push the price to ~$0.70.
4. **Counter-Trade:** Buy the now-cheap opposite outcome (~$0.30).
5. **Profit Potential:** ~$0.10 gross per share less estimated $0.03 fees/gas, netting ~$0.07/unit.

*Note: This is a speculative momentum/mean-reversion approach, not pure arbitrage. The core strategy is not for public sale but may be shared with customers.*

### Pure Arbitrage
When YES + NO token prices sum to under $1.00, purchase both:
```
Example:
YES @ $0.48 + NO @ $0.49 = $0.97 cost
Guaranteed payout = $1.00
Profit = $0.03 per dollar (3.09%)
```

---

## Status

- Live trading enabled
- Dashboard accessible via your configured domain

---

## Features

- Real-time WebSocket price monitoring (6 parallel connections, covers up to 1500 markets)
- Automatic arbitrage detection & execution
- **Low-latency async order execution** (native async HTTP/2, parallel signing)
- Order monitoring with 10s timeout & auto-cancel
- Market filtering: by liquidity (default $10k+) and event resolution (default 7 days)
- Web dashboard with live visibility (HTTPS, auto SSL)
- Slack trades notifications
- SOCKS5 proxy support for geo-restricted execution

---

## Setup

```bash
# Clone repo
git clone https://github.com/VectorPulser/polymarket-trading-bot.git
cd rarb

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Generate Polymarket API credentials
python -c "
from py_clob_client.client import ClobClient
import os
client = ClobClient('https://clob.polymarket.com', key=os.environ['PRIVATE_KEY'], chain_id=137)
creds = client.create_or_derive_api_creds()
print(f'POLY_API_KEY={creds.api_key}')
print(f'POLY_API_SECRET={creds.api_secret}')
print(f'POLY_API_PASSPHRASE={creds.api_passphrase}')
"

# Approve contracts (one-time)
python scripts/approve_usdc.py

# Run bot
rarb run --live --realtime
```

---

## Configuration

Key environment variables in `.env`:

```bash
# Wallet
PRIVATE_KEY=0x...                      # Your wallet private key
WALLET_ADDRESS=0x...                   # Your wallet address

# Polymarket L2 API Credentials (see setup)
POLY_API_KEY=...
POLY_API_SECRET=...
POLY_API_PASSPHRASE=...

# Trading parameters
MIN_PROFIT_THRESHOLD=0.005             # 0.5% min profit
MAX_POSITION_SIZE=100                  # $100 max per trade
MIN_LIQUIDITY_USD=10000                # $10k min market liquidity
MAX_DAYS_UNTIL_RESOLUTION=7            # Ignore long-resolving markets
NUM_WS_CONNECTIONS=6                   # WebSockets (250 markets ea)
DRY_RUN=true                           # Set false to enable live trading

# Dashboard (optional)
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=...
```
Refer to `.env.example` for a complete list of options.

---

## Contract Approvals

Prior to trading, allow Polymarket contracts to spend your USDC.e:

```bash
# Requires PRIVATE_KEY set in your environment
python scripts/approve_usdc.py
```
Approves:
- CTF Exchange
- Neg Risk Exchange
- Conditional Tokens
- Neg Risk Adapter

---

## Geo-Restrictions & Proxy Setup

U.S. IPs are blocked for order placement. Recommended:  
- **Bot server (us-east-1):** For fast WebSocket data
- **Proxy server (ca-central-1 Montréal):** SOCKS5 proxy for order routing

Configure your proxy in `.env`:
```bash
SOCKS5_PROXY_HOST=your-proxy-ip
SOCKS5_PROXY_PORT=1080
SOCKS5_PROXY_USER=rarb
SOCKS5_PROXY_PASS=your-password
```
Deployment scripts: see `infra/` (OpenTofu + Ansible).

---

## Documentation

For product requirements and technical architecture, see [PRD.md](PRD.md).

---

## License

This project is licensed under the MIT License.

---

Let me know if you need further refinement or a different format!
