# test_e2e_integration.py – End-to-End Integration Tests (Phase 4)
# TDD Phase: Validates full chain: Button → Controller → IBClient → UI Update
#
# These tests simulate the COMPLETE flow using mocked IB Gateway,
# verifying that all 3 layers work together correctly.
#
# Test Plan Reference: test_plan.md §6

import sys
import time
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

from ib_controller import IBController, ConnectionStatus
from ib_exceptions import IBConnectionError, IBDataError, AccountData


# =============================================================================
# E2E: Full Chain Integration Tests
# =============================================================================


class TestE2EFullChain:
    """End-to-end tests simulating Button → Controller → Client → UI."""

    @patch("ib_controller.IBClient")
    def test_e2e_happy_path_full_flow(self, MockIBClient):
        """
        E2E HAPPY PATH:
        1. User clicks Sync → Controller starts fetch
        2. IBClient connects, fetches summary + commissions, disconnects
        3. Controller calls on_data_received with complete AccountData
        4. UI panel receives data with correct values

        Verifies entire chain works without real IB Gateway.
        """
        # Arrange – Mock UI root with .after() that executes immediately
        mock_root = MagicMock()
        received_data = {}

        def mock_after(ms, callback, *args):
            """Simulate root.after() by calling callback immediately."""
            callback(*args)

        mock_root.after.side_effect = mock_after

        def on_data(data):
            received_data["result"] = data

        def on_error(msg):
            received_data["error"] = msg

        # Mock IBClient behavior (simulates IB Gateway response)
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = AccountData(
            cash=15230.50,
            net_liquidation=28450.75,
            buying_power=56901.50,
            margin_req=4200.00,
            daily_commissions=0.0,
            timestamp=datetime.now(),
            is_partial=False,
            missing_fields=[],
        )
        mock_client.get_daily_commissions.return_value = 18.60
        MockIBClient.return_value = mock_client

        # Act – simulate user clicking "Sync IB"
        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
        )
        controller.fetch_account_data()

        # Wait for background thread
        time.sleep(0.5)

        # Assert – full chain verification
        # 1. IBClient was used correctly
        mock_client.connect.assert_called_once_with(
            host="127.0.0.1", port=7496, client_id=1, timeout=5
        )
        mock_client.get_account_summary.assert_called_once()
        mock_client.get_daily_commissions.assert_called_once()
        mock_client.disconnect.assert_called_once()

        # 2. Controller state is correct
        assert controller.status == ConnectionStatus.CONNECTED
        assert controller.is_busy is False

        # 3. UI received the data
        assert "result" in received_data
        data = received_data["result"]
        assert data.cash == 15230.50
        assert data.net_liquidation == 28450.75
        assert data.buying_power == 56901.50
        assert data.margin_req == 4200.00
        assert data.daily_commissions == 18.60
        assert data.is_partial is False

        # 4. No error was triggered
        assert "error" not in received_data

    @patch("ib_controller.IBClient")
    def test_e2e_gateway_offline(self, MockIBClient):
        """
        E2E ERROR PATH – IB Gateway not running:
        1. User clicks Sync
        2. IBClient.connect() fails with ConnectionRefusedError
        3. Controller catches, maps to Hebrew message
        4. UI receives error message (not a crash)
        """
        mock_root = MagicMock()
        received_data = {}

        def mock_after(ms, callback, *args):
            callback(*args)

        mock_root.after.side_effect = mock_after

        def on_data(data):
            received_data["result"] = data

        def on_error(msg):
            received_data["error"] = msg

        # Mock IBClient – connection refused
        mock_client = MagicMock()
        mock_client.connect.side_effect = IBConnectionError(
            "IB Gateway לא פעיל. הפעל ונסה שוב.", error_code=None
        )
        MockIBClient.return_value = mock_client

        # Act
        controller = IBController(
            root=mock_root, on_data_received=on_data, on_error=on_error
        )
        controller.fetch_account_data()
        time.sleep(0.5)

        # Assert
        assert controller.status == ConnectionStatus.ERROR
        assert controller.is_busy is False
        assert "error" in received_data
        assert "IB Gateway" in received_data["error"]
        assert "result" not in received_data
        # Disconnect should still be called (cleanup)
        mock_client.disconnect.assert_called_once()

    @patch("ib_controller.IBClient")
    def test_e2e_partial_data_flow(self, MockIBClient):
        """
        E2E PARTIAL DATA PATH:
        1. User clicks Sync
        2. IB returns only 2/4 fields (BuyingPower and Margin missing)
        3. Controller delivers partial data to UI
        4. UI receives AccountData with is_partial=True
        """
        mock_root = MagicMock()
        received_data = {}

        def mock_after(ms, callback, *args):
            callback(*args)

        mock_root.after.side_effect = mock_after

        def on_data(data):
            received_data["result"] = data

        def on_error(msg):
            received_data["error"] = msg

        # Mock IBClient – partial data
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = AccountData(
            cash=10000.0,
            net_liquidation=20000.0,
            buying_power=0.0,
            margin_req=0.0,
            daily_commissions=0.0,
            timestamp=datetime.now(),
            is_partial=True,
            missing_fields=["BuyingPower", "FullMaintMarginReq"],
        )
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        # Act
        controller = IBController(
            root=mock_root, on_data_received=on_data, on_error=on_error
        )
        controller.fetch_account_data()
        time.sleep(0.5)

        # Assert – partial data delivered successfully
        assert "result" in received_data
        data = received_data["result"]
        assert data.is_partial is True
        assert "BuyingPower" in data.missing_fields
        assert data.cash == 10000.0
        assert controller.status == ConnectionStatus.CONNECTED

    @patch("ib_controller.IBClient")
    def test_e2e_rapid_clicks_debounce(self, MockIBClient):
        """
        E2E STRESS TEST – Rapid clicks:
        1. User clicks Sync 5 times rapidly
        2. Only first fetch executes (debounce)
        3. No race conditions, no crash
        """
        mock_root = MagicMock()
        call_count = {"data": 0, "error": 0}

        def mock_after(ms, callback, *args):
            callback(*args)

        mock_root.after.side_effect = mock_after

        def on_data(data):
            call_count["data"] += 1

        def on_error(msg):
            call_count["error"] += 1

        # Mock IBClient – slow connection (simulates real latency)
        mock_client = MagicMock()
        mock_client.connect.side_effect = lambda *a, **kw: time.sleep(0.3)
        mock_client.get_account_summary.return_value = AccountData(
            cash=5000.0, net_liquidation=10000.0, buying_power=20000.0,
            margin_req=1000.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        # Act – simulate 5 rapid clicks
        controller = IBController(
            root=mock_root, on_data_received=on_data, on_error=on_error
        )
        for _ in range(5):
            controller.fetch_account_data()
            time.sleep(0.02)  # 20ms between clicks

        # Wait for single fetch to complete
        time.sleep(1.0)

        # Assert – only ONE fetch executed
        assert mock_client.connect.call_count == 1
        assert call_count["data"] == 1
        assert call_count["error"] == 0
        assert controller.is_busy is False

    @patch("ib_controller.IBClient")
    def test_e2e_disconnect_mid_fetch(self, MockIBClient):
        """
        E2E EDGE CASE – IB disconnects during data fetch:
        1. Connect succeeds
        2. get_account_summary() raises IBDataError
        3. Controller handles gracefully, reports error to UI
        """
        mock_root = MagicMock()
        received_data = {}

        def mock_after(ms, callback, *args):
            callback(*args)

        mock_root.after.side_effect = mock_after

        def on_data(data):
            received_data["result"] = data

        def on_error(msg):
            received_data["error"] = msg

        # Mock IBClient – connect OK, but data fetch fails
        mock_client = MagicMock()
        mock_client.connect.return_value = None  # Connect succeeds
        mock_client.get_account_summary.side_effect = IBDataError(
            "לא התקבלו נתונים מ-IB.", partial_data=None
        )
        MockIBClient.return_value = mock_client

        # Act
        controller = IBController(
            root=mock_root, on_data_received=on_data, on_error=on_error
        )
        controller.fetch_account_data()
        time.sleep(0.5)

        # Assert
        assert controller.status == ConnectionStatus.ERROR
        assert "error" in received_data
        assert "נתונים" in received_data["error"]
        mock_client.disconnect.assert_called_once()

    @patch("ib_controller.IBClient")
    def test_e2e_second_fetch_after_error_recovers(self, MockIBClient):
        """
        E2E RECOVERY:
        1. First fetch fails (Gateway offline)
        2. User fixes Gateway, clicks Sync again
        3. Second fetch succeeds
        4. UI shows fresh data, error cleared
        """
        mock_root = MagicMock()
        results = []

        def mock_after(ms, callback, *args):
            callback(*args)

        mock_root.after.side_effect = mock_after

        def on_data(data):
            results.append(("data", data))

        def on_error(msg):
            results.append(("error", msg))

        # Mock IBClient – first call fails, second succeeds
        mock_client = MagicMock()
        call_sequence = [
            IBConnectionError("IB Gateway לא פעיל.", error_code=None),  # First call
            None,  # Second call succeeds
        ]
        mock_client.connect.side_effect = call_sequence
        mock_client.get_account_summary.return_value = AccountData(
            cash=9999.0, net_liquidation=19999.0, buying_power=39999.0,
            margin_req=2000.0, daily_commissions=3.50,
        )
        mock_client.get_daily_commissions.return_value = 3.50
        MockIBClient.return_value = mock_client

        controller = IBController(
            root=mock_root, on_data_received=on_data, on_error=on_error
        )

        # First fetch – fails
        controller.fetch_account_data()
        time.sleep(0.5)
        assert controller.status == ConnectionStatus.ERROR
        assert len(results) == 1
        assert results[0][0] == "error"

        # Second fetch – succeeds (user fixed Gateway)
        controller.fetch_account_data()
        time.sleep(0.5)
        assert controller.status == ConnectionStatus.CONNECTED
        assert len(results) == 2
        assert results[1][0] == "data"
        assert results[1][1].cash == 9999.0
