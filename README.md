# Polymarket Bot | Polymarket Trading Bot | Polymarket Arbitrage Bot

Polymarket Bot, Polymarket Trading Bot, Polymarket Arbitrage Bot, Polymarket Automatic Trading Bot
Advanced Polymarket Trading Bot (Python) – A high-performance automated trading system for Polymarket prediction markets, built in Python. Supports gasless trading, real-time WebSocket market data streaming, and fully automated arbitrage and volatility strategies optimized for short-term and high-frequency trading environments. Designed for efficient capital allocation, low-latency execution, and scalable quantitative crypto trading.

Status: Live trading enabled. Dashboard available at configured domain.

Read article here: https://medium.com/@benjamin.bigdev/high-roi-polymarket-arbitrage-in-2026-programmatic-dutch-book-strategies-bots-and-portfolio-41372221bb79


## Contact info



Telegram: [@BenjaminCup](https://t.me/BenjaminCup)


## Video

https://github.com/user-attachments/assets/f06d66ee-4408-4076-91c3-5476d780cf7a

## Strategy

Core Steps (Binary Yes/No market):

Identify a directional conviction (“Yes” or “No” is undervalued).
Execute a sizable buy of the favored outcome when its price is around $0.60 (opposite side therefore ~$0.40). In thin order books this visibly moves the favored price to $0.61–$0.62 and the opposite to $0.38–$0.39.
Rely on other participants observing the price action (and possibly your on-chain wallet activity) to interpret it as strong conviction → retail/FOMO buying pushes the favored outcome to ~$0.70 and the opposite to ~$0.30.
At the widened spread, buy the now-cheap opposite outcome at ~$0.30.
Claimed P&L: $0.10 gross per share equivalent (difference created by the spread widening you helped engineer) minus ~$0.03 in assumed fees/gas → net ~$0.07 per unit.

This is not arbitrage. It is a speculative momentum + mean-reversion hybrid that attempts to influence short-term order flow.

Strategy is Not for sale but going to share it to customers.

Pure arbitrage: when YES + NO token prices sum to less than $1.00, buy both. One token always pays out $1.00, guaranteeing profit regardless of outcome.

```
Example:
YES @ $0.48 + NO @ $0.49 = $0.97 cost
Payout = $1.00 (guaranteed)
Profit = $0.03 per dollar (3.09%)
```
## Status

Live trading enabled. Dashboard available at configured domain.

## Features

- Real-time WebSocket price monitoring (6 parallel connections, up to 1500 markets)
- Automatic arbitrage detection and execution
- **Low-latency async order execution** (native async HTTP with HTTP/2, parallel order signing)
- Order monitoring with 10-second timeout and auto-cancellation
- Market filtering by liquidity ($10k+ default) and resolution date (7 days default)
- Web dashboard with live order visibility (HTTPS with auto SSL)
- Slack notifications for trades
- SOCKS5 proxy support for geo-restricted order placement

## Setup

```bash
# Clone
git clone https://github.com/VectorPulser/polymarket-trading-bot.git
cd rarb

# Install dependencies
pip install -e .

# Configure
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

# Approve Polymarket contracts (one-time setup)
python scripts/approve_usdc.py

# Run
rarb run --live --realtime
```

## Configuration

Required environment variables:

```bash
# Wallet
PRIVATE_KEY=0x...                    # Your wallet private key
WALLET_ADDRESS=0x...                 # Your wallet address

# Polymarket L2 API Credentials (generate with script above)
POLY_API_KEY=...
POLY_API_SECRET=...
POLY_API_PASSPHRASE=...

# Trading Parameters
MIN_PROFIT_THRESHOLD=0.005           # 0.5% minimum profit
MAX_POSITION_SIZE=100                # Max $100 per trade
MIN_LIQUIDITY_USD=10000              # $10k minimum market liquidity
MAX_DAYS_UNTIL_RESOLUTION=7          # Skip markets resolving later
NUM_WS_CONNECTIONS=6                 # WebSocket connections (250 markets each)
DRY_RUN=true                         # Set to false for live trading

# Dashboard (optional - omit for no auth)
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=...
```

See `.env.example` for all available options.

## Contract Approvals

Before trading, you must approve Polymarket's smart contracts to spend your USDC.e:

```bash
# Run the approval script (requires PRIVATE_KEY in environment)
python scripts/approve_usdc.py
```

This approves:
- CTF Exchange
- Neg Risk Exchange
- Conditional Tokens
- Neg Risk Adapter

## Geo-Restrictions

Polymarket blocks US IP addresses for order placement. The recommended architecture:

- **Bot server (us-east-1)**: Low-latency WebSocket connection for price monitoring
- **Proxy server (ca-central-1 Montreal)**: SOCKS5 proxy for order placement

Configure the proxy in your `.env`:
```bash
SOCKS5_PROXY_HOST=your-proxy-ip
SOCKS5_PROXY_PORT=1080
SOCKS5_PROXY_USER=rarb
SOCKS5_PROXY_PASS=your-password
```

See `infra/` for OpenTofu + Ansible deployment scripts.



## Documentation

See [PRD.md](PRD.md) for full product requirements and technical architecture.

## License

MIT



