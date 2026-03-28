"""
broker_backend.py - Alpaca + Interactive Brokers CLI wrapper

Provides unified access to two broker platforms:

Alpaca:
  - Commission-free stock trading via REST API
  - Paper trading and live trading
  - API docs: https://docs.alpaca.markets/
  - Install: pip install alpaca-trade-api

Interactive Brokers (IBKR):
  - Professional trading via Trader Workstation API
  - Uses ib_insync library (socket-based)
  - Requires TWS or IB Gateway running
  - Install: pip install ib_insync

Principles:
  - MUST call real broker APIs, not reimplement
  - API keys are required - error clearly if not configured
  - Both platforms have different APIs but similar concepts
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

BROKER_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a broker command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Python runner
# -------------------------------------------------------------------

def _run_python(script: str, timeout: int = 60) -> CommandResult:
    """Run a Python script and return result."""
    python = Path(sys.executable)
    start = time.time()

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            proc = subprocess.run(
                [str(python), script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            duration = time.time() - start

            return CommandResult(
                success=proc.returncode == 0,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error="Script timed out after {}s".format(timeout),
            returncode=-1,
            duration_seconds=timeout,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

def get_version() -> dict:
    """Get broker API version info."""
    if os.environ.get("BROKER_MOCK"):
        return {"success": True, "alpaca": "3.15.0", "ib": "0.6.30"}

    result = _run_python("""
try:
    import alpaca_trade_api
    print(alpaca_trade_api.__version__)
except:
    print('not installed')
""")
    alpaca_ver = result.output.strip() if result.success else "not installed"

    result2 = _run_python("""
try:
    import ib_insync
    print(ib_insync.__version__)
except:
    print('not installed')
""")
    ib_ver = result2.output.strip() if result2.success else "not installed"

    return {
        "success": True,
        "alpaca": alpaca_ver,
        "ib": ib_ver,
    }


# -------------------------------------------------------------------
# Alpaca operations
# -------------------------------------------------------------------

def _alpaca_get(key: str, endpoint: str) -> dict:
    """Make GET request to Alpaca API."""
    if os.environ.get("BROKER_MOCK"):
        return _alpaca_mock(endpoint)

    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_API_SECRET", "")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not api_secret:
        return {"success": False, "error": "ALPACA_API_KEY and ALPACA_API_SECRET must be set"}

    script = """
import requests
import os

key = os.environ.get("ALPACA_API_KEY")
secret = os.environ.get("ALPACA_API_SECRET")
base = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

headers = {{
    "APCA-API-KEY-ID": key,
    "APCA-API-SECRET-KEY": secret,
}}

r = requests.get(base + "{endpoint}", headers=headers)
print(r.text)
""".format(endpoint=endpoint)

    result = _run_python(script)
    if result.success:
        try:
            return {"success": True, "data": json.loads(result.output)}
        except Exception:
            return {"success": False, "error": "Failed to parse response"}
    return {"success": False, "error": result.error}


def _alpaca_post(key: str, endpoint: str, data: dict) -> dict:
    """Make POST request to Alpaca API."""
    if os.environ.get("BROKER_MOCK"):
        return _alpaca_mock(endpoint, data)

    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_API_SECRET", "")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not api_secret:
        return {"success": False, "error": "ALPACA_API_KEY and ALPACA_API_SECRET must be set"}

    body = json.dumps(data)
    script = """
import requests
import os
import json

key = os.environ.get("ALPACA_API_KEY")
secret = os.environ.get("ALPACA_API_SECRET")
base = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

headers = {{
    "APCA-API-KEY-ID": key,
    "APCA-API-SECRET-KEY": secret,
    "Content-Type": "application/json",
}}

r = requests.post(base + "{endpoint}", headers=headers, data='{body}')
print(r.text)
""".format(endpoint=endpoint, body=body)

    result = _run_python(script)
    if result.success:
        try:
            return {"success": True, "data": json.loads(result.output)}
        except Exception:
            return {"success": False, "error": "Failed to parse response"}
    return {"success": False, "error": result.error}


def _alpaca_mock(endpoint: str, data: dict = None) -> dict:
    """Return mock data for Alpaca endpoints."""
    mock_account = {
        "id": "mock-account-id",
        "account_number": "MA123456",
        "status": "ACTIVE",
        "currency": "USD",
        "buying_power": "50000.00",
        "cash": "25000.00",
        "portfolio_value": "50000.00",
        "equity": "50000.00",
        "last_equity": "49500.00",
    }

    mock_positions = [
        {"symbol": "AAPL", "qty": "10", "market_value": "1800.00", "unrealized_pl": "150.00"},
        {"symbol": "MSFT", "qty": "5", "market_value": "2000.00", "unrealized_pl": "80.00"},
    ]

    mock_orders = [
        {"id": "order-1", "symbol": "AAPL", "qty": "10", "side": "buy", "status": "filled", "filled_qty": "10"},
        {"id": "order-2", "symbol": "GOOGL", "qty": "5", "side": "sell", "status": "pending", "filled_qty": "0"},
    ]

    if "account" in endpoint:
        return {"success": True, "data": mock_account}
    elif "positions" in endpoint:
        return {"success": True, "data": mock_positions}
    elif "orders" in endpoint:
        return {"success": True, "data": mock_orders}
    return {"success": True, "data": {}}


# -------------------------------------------------------------------
# Account
# ------------------------------------------------------------------

def alpaca_account() -> dict:
    """Get Alpaca account information."""
    return _alpaca_get("account", "/v2/account")


def alpaca_list_positions() -> dict:
    """List open positions."""
    return _alpaca_get("positions", "/v2/positions")


# -------------------------------------------------------------------
# Orders
# ------------------------------------------------------------------

def alpaca_list_orders(status: str = "all", limit: int = 50) -> dict:
    """List orders."""
    return _alpaca_get("orders", "/v2/orders?status={}&limit={}".format(status, limit))


def alpaca_place_order(
    symbol: str,
    qty: int,
    side: str,  # buy or sell
    order_type: str = "market",
    time_in_force: str = "day",
    limit_price: Optional[float] = None,
) -> dict:
    """
    Place an order on Alpaca.

    Args:
        symbol: Stock symbol (e.g. AAPL)
        qty: Number of shares
        side: 'buy' or 'sell'
        order_type: 'market' or 'limit'
        time_in_force: 'day', 'gtc', 'opg', 'cls'
        limit_price: Limit price for limit orders

    Returns:
        dict with order info
    """
    data = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }
    if limit_price:
        data["limit_price"] = str(limit_price)

    return _alpaca_post("orders", "/v2/orders", data)


def alpaca_cancel_order(order_id: str) -> dict:
    """Cancel an order."""
    if os.environ.get("BROKER_MOCK"):
        return {"success": True, "message": "Order {} cancelled".format(order_id)}

    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_API_SECRET", "")

    if not api_key:
        return {"success": False, "error": "ALPACA_API_KEY not set"}

    script = """
import requests
import os

key = os.environ.get("ALPACA_API_KEY")
secret = os.environ.get("ALPACA_API_SECRET")

headers = {{
    "APCA-API-KEY-ID": key,
    "APCA-API-SECRET-KEY": secret,
}}

r = requests.delete(
    "https://paper-api.alpaca.markets/v2/orders/{order_id}",
    headers=headers
)
print(r.status_code)
""".format(order_id=order_id)

    result = _run_python(script)
    return {"success": result.returncode == 0, "code": result.returncode}


# -------------------------------------------------------------------
# Market data
# ------------------------------------------------------------------

def alpaca_quote(symbol: str) -> dict:
    """Get quote for a symbol."""
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_API_SECRET", "")

    if os.environ.get("BROKER_MOCK"):
        return {
            "success": True,
            "symbol": symbol,
            "bid": 150.00,
            "ask": 150.05,
            "last": 150.02,
            "volume": 1000000,
        }

    if not api_key:
        return {"success": False, "error": "ALPACA_API_KEY not set"}

    script = """
import requests

key = "{key}"
secret = "{secret}"

headers = {{
    "APCA-API-KEY-ID": key,
    "APCA-API-SECRET-KEY": secret,
}}

r = requests.get(
    "https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest",
    headers=headers
)
print(r.text)
""".format(key=api_key, secret=api_secret, symbol=symbol)

    result = _run_python(script)
    if result.success:
        try:
            return {"success": True, "data": json.loads(result.output)}
        except Exception:
            return {"success": False, "error": "Failed to parse response"}
    return {"success": False, "error": result.error}


# -------------------------------------------------------------------
# IB operations (simplified via ib_insync)
# ------------------------------------------------------------------

def ib_account() -> dict:
    """Get Interactive Brokers account info via ib_insync."""
    if os.environ.get("BROKER_MOCK"):
        return {
            "success": True,
            "account": "DU123456",
            "cash": 25000.00,
            "portfolio_value": 50000.00,
            "buying_power": 100000.00,
        }

    script = """
from ib_insync import IB
import os

ib = IB()
try:
    port = int(os.environ.get("IB_PORT", 7497))
    ib.connect('127.0.0.1', port, clientId=1)
    accts = ib.managedAccounts()
    if accts:
        acct = ib.accountSummary(accts[0])
        summary = {item.tag: item.value for item in acct}
        print(summary.get('NetLiquidation', ''))
except Exception as e:
    print('ERROR:' + str(e))
"""

    result = _run_python(script)
    if result.success and not result.output.startswith("ERROR"):
        return {"success": True, "account": result.output.strip()}
    return {"success": False, "error": result.error or result.output}


def ib_list_positions() -> dict:
    """List IB positions."""
    if os.environ.get("BROKER_MOCK"):
        return {
            "success": True,
            "positions": [
                {"symbol": "AAPL", "position": 10, "market_value": 1800.00},
                {"symbol": "MSFT", "position": 5, "market_value": 2000.00},
            ],
        }

    script = """
from ib_insync import IB
import json

ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=1)
    positions = ib.positions()
    result = []
    for pos in positions:
        result.append({{
            'symbol': pos.contract.symbol,
            'position': pos.position,
            'market_value': ib.portfolioValue(pos.contract),
        }})
    print(json.dumps(result))
except Exception as e:
    print('ERROR:' + str(e))
"""

    result = _run_python(script)
    if result.success and not result.output.startswith("ERROR"):
        try:
            return {"success": True, "positions": json.loads(result.output)}
        except Exception:
            pass
    return {"success": False, "error": result.error or result.output}
