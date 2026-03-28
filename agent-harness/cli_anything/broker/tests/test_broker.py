"""
test_core.py - Unit tests for cli-anything-broker

Tests Broker backend with synthetic data.
No real broker API required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/broker/tests/test_core.py -v
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.broker.utils import broker_backend as bb


class TestCommandResult:
    def test_fields(self):
        r = bb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True

    def test_failure(self):
        r = bb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False


class TestVersion:
    def test_get_version_mock(self):
        v = bb.get_version()
        assert v["success"] is True
        assert "alpaca" in v


class TestAlpacaAccount:
    def test_account_mock(self):
        r = bb.alpaca_account()
        assert r["success"] is True
        assert "account_number" in r["data"]
        assert r["data"]["status"] == "ACTIVE"


class TestAlpacaPositions:
    def test_positions_mock(self):
        r = bb.alpaca_list_positions()
        assert r["success"] is True
        positions = r["data"]
        assert len(positions) >= 1
        assert positions[0]["symbol"] == "AAPL"


class TestAlpacaOrders:
    def test_list_orders_mock(self):
        r = bb.alpaca_list_orders()
        assert r["success"] is True
        orders = r["data"]
        assert len(orders) >= 1


class TestAlpacaPlaceOrder:
    def test_place_order_missing_key_mock(self):
        # Even without API key, mock returns success
        r = bb.alpaca_place_order("AAPL", 10, "buy")
        # Mock returns success
        assert r.get("success") or r.get("data", {}).get("id") == "mock-order-id"


class TestAlpacaCancel:
    def test_cancel_mock(self):
        r = bb.alpaca_cancel_order("order-1")
        assert r["success"] is True


class TestAlpacaQuote:
    def test_quote_mock(self):
        r = bb.alpaca_quote("AAPL")
        assert r["success"] is True
        assert "bid" in r


class TestIB:
    def test_ib_account_mock(self):
        r = bb.ib_account()
        assert r["success"] is True
        assert "account" in r

    def test_ib_positions_mock(self):
        r = bb.ib_list_positions()
        assert r["success"] is True
        assert "positions" in r


class TestMock:
    def test_mock_env_set(self):
        assert os.environ.get("BROKER_MOCK") == "1"
