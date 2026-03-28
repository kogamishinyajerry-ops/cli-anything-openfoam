"""
broker_cli.py - Alpaca + Interactive Brokers CLI harness

Usage:
  broker account                     Show account info
  broker positions                   List open positions
  broker orders [status]            List orders (default: open)
  broker order buy <sym> <qty>      Place buy order
  broker order sell <sym> <qty>     Place sell order
  broker cancel <order_id>          Cancel an order
  broker quote <symbol>             Get quote
  broker version                    Show versions
"""

from __future__ import annotations

import click
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.broker.utils import broker_backend as bb


@click.group()
@click.version_option(version=bb.BROKER_VERSION, prog_name="broker")
def cli():
    """Broker CLI (Alpaca + Interactive Brokers)."""
    pass


# ------------------------------------------------------------------
# Account
# ------------------------------------------------------------------

@cli.command("account")
@click.option("--broker", default="alpaca", type=click.Choice(["alpaca", "ib"]))
@click.option("--json", "use_json", is_flag=True)
def account_cmd(broker: str, use_json: bool):
    """Show account information."""
    if broker == "alpaca":
        result = bb.alpaca_account()
    else:
        result = bb.ib_account()

    if result.get("success"):
        if use_json:
            click.echo(json.dumps(result.get("data", result), indent=2))
        else:
            data = result.get("data", result)
            for k, v in data.items():
                click.echo("  {:20s}: {}".format(k, v))
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("positions")
@click.option("--broker", default="alpaca", type=click.Choice(["alpaca", "ib"]))
@click.option("--json", "use_json", is_flag=True)
def positions_cmd(broker: str, use_json: bool):
    """List open positions."""
    if broker == "alpaca":
        result = bb.alpaca_list_positions()
    else:
        result = bb.ib_list_positions()

    if result.get("success"):
        positions = result.get("data", result.get("positions", []))
        if use_json:
            click.echo(json.dumps(positions, indent=2))
        else:
            if isinstance(positions, list) and len(positions) > 0:
                click.echo("{:<10s} {:>8s} {:>12s} {:>12s}".format(
                    "SYMBOL", "QTY", "MKT_VALUE", "P/L"))
                for p in positions:
                    sym = p.get("symbol", "?")
                    qty = p.get("qty", p.get("position", "?"))
                    mv = p.get("market_value", "?")
                    pl = p.get("unrealized_pl", "?")
                    click.echo("{:<10s} {:>8s} {:>12s} {:>12s}".format(
                        str(sym), str(qty), str(mv), str(pl)))
            else:
                click.echo("(no open positions)")
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Orders
# ------------------------------------------------------------------

@cli.group("order")
def order_group():
    """Order management commands."""
    pass


@order_group.command("list")
@click.option("--status", default="open", help="Order status (open, closed, all)")
@click.option("--json", "use_json", is_flag=True)
def order_list(status: str, use_json: bool):
    """List orders."""
    result = bb.alpaca_list_orders(status=status)
    if result.get("success"):
        orders = result.get("data", [])
        if use_json:
            click.echo(json.dumps(orders, indent=2))
        else:
            if orders:
                click.echo("{:<12s} {:>6s} {:>5s} {:>8s} {:>10s}".format(
                    "ORDER_ID", "SYMBOL", "SIDE", "QTY", "STATUS"))
                for o in orders:
                    click.echo("{:<12s} {:>6s} {:>5s} {:>8s} {:>10s}".format(
                        o.get("id", "?")[:12], o.get("symbol", "?"),
                        o.get("side", "?")[:5], str(o.get("qty", 0)),
                        o.get("status", "?")[:10]))
            else:
                click.echo("(no orders)")
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


@order_group.command("buy")
@click.argument("symbol")
@click.argument("qty", type=int)
@click.option("--type", "order_type", default="market", type=click.Choice(["market", "limit"]))
@click.option("--limit-price", type=float, help="Limit price")
@click.option("--tif", "time_in_force", default="day", type=click.Choice(["day", "gtc", "opg", "cls"]))
def order_buy(symbol: str, qty: int, order_type: str, limit_price: float | None, time_in_force: str):
    """Place a buy order."""
    result = bb.alpaca_place_order(
        symbol=symbol.upper(),
        qty=qty,
        side="buy",
        order_type=order_type,
        time_in_force=time_in_force,
        limit_price=limit_price,
    )
    if result.get("success"):
        data = result.get("data", {})
        click.echo("[OK] Order placed")
        click.echo("  ID: {}".format(data.get("id", "unknown")))
        click.echo("  Symbol: {}".format(data.get("symbol")))
        click.echo("  Qty: {}".format(data.get("qty")))
        click.echo("  Status: {}".format(data.get("status")))
    else:
        click.echo("Error: " + result.get("error", "Failed to place order"), err=True)
        sys.exit(1)


@order_group.command("sell")
@click.argument("symbol")
@click.argument("qty", type=int)
@click.option("--type", "order_type", default="market", type=click.Choice(["market", "limit"]))
@click.option("--limit-price", type=float)
@click.option("--tif", "time_in_force", default="day", type=click.Choice(["day", "gtc", "opg", "cls"]))
def order_sell(symbol: str, qty: int, order_type: str, limit_price: float | None, time_in_force: str):
    """Place a sell order."""
    result = bb.alpaca_place_order(
        symbol=symbol.upper(),
        qty=qty,
        side="sell",
        order_type=order_type,
        time_in_force=time_in_force,
        limit_price=limit_price,
    )
    if result.get("success"):
        data = result.get("data", {})
        click.echo("[OK] Order placed")
        click.echo("  ID: {}".format(data.get("id", "unknown")))
        click.echo("  Symbol: {}".format(data.get("symbol")))
        click.echo("  Qty: {}".format(data.get("qty")))
        click.echo("  Status: {}".format(data.get("status")))
    else:
        click.echo("Error: " + result.get("error", "Failed to place order"), err=True)
        sys.exit(1)


@cli.command("cancel")
@click.argument("order_id")
def cancel_cmd(order_id: str):
    """Cancel an order."""
    result = bb.alpaca_cancel_order(order_id)
    if result.get("success") or result.get("code") == 200:
        click.echo("[OK] Order {} cancelled".format(order_id))
    else:
        click.echo("Error: Failed to cancel order {}".format(order_id), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Quote
# ------------------------------------------------------------------

@cli.command("quote")
@click.argument("symbol")
@click.option("--json", "use_json", is_flag=True)
def quote_cmd(symbol: str, use_json: bool):
    """Get quote for a symbol."""
    result = bb.alpaca_quote(symbol.upper())
    if result.get("success"):
        data = result.get("data", result)
        if use_json:
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("{}: bid={}, ask={}, last={}, vol={}".format(
                data.get("symbol", symbol),
                data.get("bid", "?"),
                data.get("ask", "?"),
                data.get("last", "?"),
                data.get("volume", "?"),
            ))
    else:
        click.echo("Error: " + result.get("error", "Unknown error"), err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# Version
# ------------------------------------------------------------------

@cli.command("version")
def version_cmd():
    """Show broker API versions."""
    info = bb.get_version()
    if info.get("success"):
        click.echo("Alpaca API: {}".format(info.get("alpaca", "not installed")))
        click.echo("IB Insync: {}".format(info.get("ib", "not installed")))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
