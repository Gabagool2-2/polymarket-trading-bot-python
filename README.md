# Polymarket Bot | Polymarket Trading Bot | Polymarket Arbitrage Bot

Polymarket Bot, Polymarket Trading Bot, Polymarket Arbitrage Bot, Polymarket Automatic Trading Bot
Advanced Polymarket Trading Bot (Python) – A high-performance automated trading system for Polymarket prediction markets, built in Python. Supports gasless trading, real-time WebSocket market data streaming, and fully automated arbitrage and volatility strategies optimized for short-term and high-frequency trading environments. Designed for efficient capital allocation, low-latency execution, and scalable quantitative crypto trading.

## Contact info

Gmail: benjamin.bigdev@gmail.com

Telegram: [@BenjaminCup](https://t.me/BenjaminCup)

X : [@benjaminccup](https://x.com/benjaminccup)


## Key Capabilities

- **Gasless Order Execution**  
  Integration with the Polymarket Builder Program for zero-gas trading.

- **Real-Time Market Data**  
  Live WebSocket streaming for orderbooks and market state updates.

- **15-Minute Market Support**  
  Native support for BTC, ETH, SOL, and XRP markets.

- **Strategy Framework**  
  Modular architecture for implementing automated trading strategies.

- **Flash Crash Detection**  
  Built-in volatility-based strategy for probability dislocations.

- **Secure Key Management**  
  PBKDF2 (480k iterations) + Fernet encrypted private key storage.

- **Developer-Friendly API**  
  Clean, extensible Python interface.

---

## Quick Start

### Installation

```bash
git clone https://github.com/Benjamin-cup/Arbitrage-bot-Polymarket.git
cd Arbitrage-bot-Polymarket
pip install -r requirements.txt
```

### Configuration

Set environment variables:

```bash
export POLY_PRIVATE_KEY=your_private_key
export POLY_PROXY_WALLET=0xYourPolymarketProxyWallet
```

> **Safe Address**: Find at [polymarket.com/settings](https://polymarket.com/settings)

### Run Strategy

```bash
python apps/flash_crash_runner.py --coin BTC
```

## Trading Strategies

### Flash Crash Strategy

Monitors 15-minute markets for sudden probability drops and executes trades automatically.

```bash
# Default settings
python apps/flash_crash_runner.py --coin BTC

# Custom parameters
python apps/flash_crash_runner.py --coin ETH --drop 0.25 --size 10 --take-profit 0.10 --stop-loss 0.05
```

**Parameters:**
- `--coin` - BTC, ETH, SOL, XRP (default: ETH)
- `--drop` - Drop threshold (default: 0.30)
- `--size` - Trade size in USDC (default: 5.0)
- `--lookback` - Detection window in seconds (default: 10)
- `--take-profit` - Take profit in dollars (default: 0.10)
- `--stop-loss` - Stop loss in dollars (default: 0.05)

### Orderbook Viewer

Real-time orderbook visualization:

```bash
python apps/orderbook_viewer.py --coin BTC --levels 5
```

## Usage Examples

### Basic Usage

```python
from src import create_bot_from_env
import asyncio

async def main():
    bot = create_bot_from_env()
    orders = await bot.get_open_orders()
    print(f"Open orders: {len(orders)}")

asyncio.run(main())
```

### Place Order

```python
from src import TradingBot, Config

bot = TradingBot(config=Config(safe_address="0x..."), private_key="0x...")
result = await bot.place_order(token_id="...", price=0.65, size=10.0, side="BUY")
```

### WebSocket Streaming

```python
from src.websocket_client import MarketWebSocket

ws = MarketWebSocket()
ws.on_book = lambda s: print(f"Price: {s.mid_price:.4f}")
await ws.subscribe(["token_id"])
await ws.run()
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POLY_PRIVATE_KEY` | Yes | Wallet private key |
| `POLY_PROXY_WALLET` | Yes | Polymarket Proxy wallet address |
| `POLY_BUILDER_API_KEY` | Optional | Builder Program API key (gasless) |
| `POLY_BUILDER_API_SECRET` | Optional | Builder Program API secret |
| `POLY_BUILDER_API_PASSPHRASE` | Optional | Builder Program passphrase |

### Config File

Create `config.yaml`:

```yaml
safe_address: "0xYourAddress"
builder:
  api_key: "your_key"
  api_secret: "your_secret"
  api_passphrase: "your_passphrase"
```

Load with: `TradingBot(config_path="config.yaml", private_key="0x...")`

## Gasless Trading

Enable gasless trading via Builder Program:

1. Apply at [polymarket.com/settings?tab=builder](https://polymarket.com/settings?tab=builder)
2. Set environment variables: `POLY_BUILDER_API_KEY`, `POLY_BUILDER_API_SECRET`, `POLY_BUILDER_API_PASSPHRASE`

The bot automatically uses gasless mode when credentials are present.



## Security

Private keys are encrypted using PBKDF2 (480,000 iterations) + Fernet symmetric encryption. Best practices:

- Never commit `.env` files
- Use a dedicated trading wallet
- Keep encrypted key files secure (permissions: 0600)

## API Reference

**TradingBot**: `place_order()`, `cancel_order()`, `get_open_orders()`, `get_trades()`, `get_order_book()`, `get_market_price()`

**MarketWebSocket**: `subscribe()`, `run()`, `disconnect()`, `get_orderbook()`, `get_mid_price()`

**GammaClient**: `get_market_info()`, `get_current_15m_market()`, `get_all_15m_markets()`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Missing credentials | Set `POLY_PRIVATE_KEY` and `POLY_PROXY_WALLET` |
| Invalid private key | Ensure 64 hex characters (0x prefix optional) |
| Order failed | Check sufficient balance |
| WebSocket errors | Verify network/firewall settings |

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Additional Tooling

I also developed a trading bot for Polymarket using **Rust**.
If you're interested, please contact me.

<img width="1917" height="942" alt="image (21)" src="https://github.com/user-attachments/assets/08a5c962-7f8b-4097-98b6-7a457daa37c9" />


**Disclaimer:** This software is provided for educational and research purposes only.
Trading prediction markets involves risk, and no guarantees of profitability are implied.
The authors assume no responsibility for financial losses incurred through use of this software.



