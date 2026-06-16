# test_ib_controller.py – Unit tests for IBController (Layer 2)
# TDD Phase: RED → GREEN cycle
#
# Test Plan Reference: test_plan.md §4
# Design Reference: design.md §3.3

import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from ib_controller import IBController, ConnectionStatus
from ib_exceptions import IBConnectionError, IBDataError, AccountData


# =============================================================================
# §4.1 ConnectionStatus Enum
# =============================================================================


class TestConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_enum_has_idle(self):
        """Enum contains IDLE state."""
        assert ConnectionStatus.IDLE is not None
        assert ConnectionStatus.IDLE.value is not None

    def test_enum_has_connecting(self):
        """Enum contains CONNECTING state."""
        assert ConnectionStatus.CONNECTING is not None

    def test_enum_has_connected(self):
        """Enum contains CONNECTED state."""
        assert ConnectionStatus.CONNECTED is not None

    def test_enum_has_error(self):
        """Enum contains ERROR state."""
        assert ConnectionStatus.ERROR is not None

    def test_enum_has_stale(self):
        """Enum contains STALE state."""
        assert ConnectionStatus.STALE is not None

    def test_enum_values_are_distinct(self):
        """All enum values are unique."""
        values = [s.value for s in ConnectionStatus]
        assert len(values) == len(set(values))


# =============================================================================
# §4.2 IBController – Initialization
# =============================================================================


class TestIBControllerInit:
    """Tests for IBController.__init__() method."""

    def test_init_status_is_idle(self):
        """
        GIVEN a fresh IBController instance
        WHEN created with valid callbacks
        THEN status is IDLE
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        on_error = MagicMock()

        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
        )

        assert controller.status == ConnectionStatus.IDLE

    def test_init_is_not_busy(self):
        """
        GIVEN a fresh IBController instance
        WHEN created
        THEN is_busy is False
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        on_error = MagicMock()

        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
        )

        assert controller.is_busy is False

    def test_init_no_last_data(self):
        """
        GIVEN a fresh IBController instance
        WHEN created
        THEN get_last_data() returns None
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        on_error = MagicMock()

        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
        )

        assert controller.get_last_data() is None

    def test_init_stores_callbacks(self):
        """
        GIVEN callbacks are passed to IBController
        WHEN created
        THEN callbacks are stored (not None)
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        on_error = MagicMock()

        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
        )

        # Controller should have stored the callbacks internally
        assert controller._on_data_received is on_data
        assert controller._on_error is on_error
        assert controller._root is mock_root

    def test_init_with_custom_config_path(self):
        """
        GIVEN a custom config path is provided
        WHEN IBController is created
        THEN it stores the config path for later use
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        on_error = MagicMock()

        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
            config_path="custom_config.json",
        )

        assert controller._config_path == "custom_config.json"

    def test_init_default_config_path(self):
        """
        GIVEN no config path is provided
        WHEN IBController is created
        THEN it uses the default config path 'config.json'
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        on_error = MagicMock()

        controller = IBController(
            root=mock_root,
            on_data_received=on_data,
            on_error=on_error,
        )

        assert controller._config_path == "config.json"



import time


# =============================================================================
# §4.3 IBController – fetch_account_data (Happy Path)
# =============================================================================


class TestIBControllerFetchHappyPath:
    """Tests for IBController.fetch_account_data() – successful flow."""

    def _make_controller(self, mock_root=None, on_data=None, on_error=None):
        """Helper to create controller with defaults."""
        return IBController(
            root=mock_root or MagicMock(),
            on_data_received=on_data or MagicMock(),
            on_error=on_error or MagicMock(),
        )

    @patch("ib_controller.IBClient")
    def test_fetch_sets_busy_immediately(self, MockIBClient):
        """
        GIVEN controller is idle
        WHEN fetch_account_data() is called
        THEN is_busy becomes True immediately
        """
        mock_client = MagicMock()
        # Make connect slow so thread doesn't finish before assertion
        mock_client.connect.side_effect = lambda *a, **kw: time.sleep(0.5)
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = self._make_controller()
        controller.fetch_account_data()
        time.sleep(0.05)  # Let thread start but not finish

        assert controller.is_busy is True

    @patch("ib_controller.IBClient")
    def test_fetch_sets_status_connecting(self, MockIBClient):
        """
        GIVEN controller is idle
        WHEN fetch_account_data() is called
        THEN status changes to CONNECTING
        """
        mock_client = MagicMock()
        # Make connect slow so thread doesn't finish before assertion
        mock_client.connect.side_effect = lambda *a, **kw: time.sleep(0.5)
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = self._make_controller()
        controller.fetch_account_data()
        time.sleep(0.05)  # Let thread start but not finish

        assert controller.status == ConnectionStatus.CONNECTING

    @patch("ib_controller.IBClient")
    def test_fetch_calls_on_data_received_on_success(self, MockIBClient):
        """
        GIVEN IBClient returns valid AccountData
        WHEN fetch_account_data() completes
        THEN on_data_received callback is scheduled via root.after()
        """
        mock_root = MagicMock()
        on_data = MagicMock()
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 5.50
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=on_data, on_error=MagicMock())
        controller.fetch_account_data()

        # Wait for background thread to finish
        time.sleep(0.3)

        # Verify root.after was called (schedules callback on main thread)
        mock_root.after.assert_called()

    @patch("ib_controller.IBClient")
    def test_fetch_status_connected_after_success(self, MockIBClient):
        """
        GIVEN IBClient returns valid data
        WHEN fetch_account_data() completes
        THEN status becomes CONNECTED
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 5.50
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()

        time.sleep(0.3)
        assert controller.status == ConnectionStatus.CONNECTED

    @patch("ib_controller.IBClient")
    def test_fetch_resets_busy_after_success(self, MockIBClient):
        """
        GIVEN a fetch is in progress
        WHEN it completes successfully
        THEN is_busy returns to False
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 5.50
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()

        time.sleep(0.3)
        assert controller.is_busy is False

    @patch("ib_controller.IBClient")
    def test_fetch_stores_last_data(self, MockIBClient):
        """
        GIVEN a successful fetch
        WHEN completed
        THEN get_last_data() returns the fetched AccountData
        """
        mock_root = MagicMock()
        expected_data = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=5.50,
        )
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = expected_data
        mock_client.get_daily_commissions.return_value = 5.50
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()

        time.sleep(0.3)
        result = controller.get_last_data()
        assert result is not None
        assert result.cash == 1000.0
        assert result.daily_commissions == 5.50


# =============================================================================
# §4.4 IBController – fetch_account_data (Error Path)
# =============================================================================


class TestIBControllerFetchErrorPath:
    """Tests for IBController.fetch_account_data() – failure scenarios."""

    @patch("ib_controller.IBClient")
    def test_fetch_connection_error_calls_on_error(self, MockIBClient):
        """
        GIVEN IBClient.connect() raises IBConnectionError
        WHEN fetch_account_data() runs
        THEN on_error callback is scheduled via root.after()
        """
        mock_root = MagicMock()
        on_error = MagicMock()
        mock_client = MagicMock()
        mock_client.connect.side_effect = IBConnectionError("IB Gateway לא פעיל.", error_code=None)
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=on_error)
        controller.fetch_account_data()

        time.sleep(0.3)
        # root.after should have been called with the error callback
        mock_root.after.assert_called()

    @patch("ib_controller.IBClient")
    def test_fetch_error_sets_status_error(self, MockIBClient):
        """
        GIVEN IBClient raises an exception
        WHEN fetch_account_data() runs
        THEN status becomes ERROR
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        mock_client.connect.side_effect = IBConnectionError("fail", error_code=None)
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()

        time.sleep(0.3)
        assert controller.status == ConnectionStatus.ERROR

    @patch("ib_controller.IBClient")
    def test_fetch_error_resets_busy(self, MockIBClient):
        """
        GIVEN IBClient raises an exception
        WHEN fetch_account_data() completes (with error)
        THEN is_busy returns to False
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        mock_client.connect.side_effect = IBConnectionError("fail", error_code=None)
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()

        time.sleep(0.3)
        assert controller.is_busy is False

    @patch("ib_controller.IBClient")
    def test_fetch_unexpected_error_calls_on_error(self, MockIBClient):
        """
        GIVEN IBClient raises an unexpected RuntimeError
        WHEN fetch_account_data() runs
        THEN on_error is still called (generic message), no crash
        """
        mock_root = MagicMock()
        on_error = MagicMock()
        mock_client = MagicMock()
        mock_client.connect.side_effect = RuntimeError("Something unexpected")
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=on_error)
        controller.fetch_account_data()

        time.sleep(0.3)
        mock_root.after.assert_called()
        assert controller.status == ConnectionStatus.ERROR


# =============================================================================
# §4.5 IBController – Debounce Logic
# =============================================================================


class TestIBControllerDebounce:
    """Tests for debounce (reject second call while busy)."""

    @patch("ib_controller.IBClient")
    def test_debounce_rejects_second_call(self, MockIBClient):
        """
        GIVEN a fetch is already in progress (is_busy=True)
        WHEN fetch_account_data() is called again
        THEN the second call does NOT spawn a new thread (only 1 connect call)
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        # Make connect slow so we can call fetch twice while first is running
        mock_client.connect.side_effect = lambda *a, **kw: time.sleep(0.5)
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())

        # First call
        controller.fetch_account_data()
        time.sleep(0.05)  # Let thread start

        # Second call while first is running
        controller.fetch_account_data()

        time.sleep(0.8)  # Wait for first to finish

        # connect should only have been called once
        assert mock_client.connect.call_count == 1

    @patch("ib_controller.IBClient")
    def test_debounce_allows_after_completion(self, MockIBClient):
        """
        GIVEN first fetch has completed (is_busy=False)
        WHEN fetch_account_data() is called again
        THEN the second call executes normally
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        mock_client.get_account_summary.return_value = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
        )
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())

        # First fetch
        controller.fetch_account_data()
        time.sleep(0.3)
        assert controller.is_busy is False

        # Second fetch after completion
        controller.fetch_account_data()
        time.sleep(0.3)

        # connect called twice (once per fetch)
        assert mock_client.connect.call_count == 2



from datetime import timedelta


# =============================================================================
# §4.6 IBController – Stale Data Detection
# =============================================================================


class TestIBControllerStaleDetection:
    """Tests for stale data detection based on timestamp TTL."""

    @patch("ib_controller.IBClient")
    def test_data_not_stale_within_threshold(self, MockIBClient):
        """
        GIVEN data was fetched 2 minutes ago
        AND stale threshold is 5 minutes (default)
        WHEN checking staleness
        THEN status remains CONNECTED (not STALE)
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        # Data fetched "now" (fresh)
        fresh_data = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
            timestamp=datetime.now() - timedelta(minutes=2),
        )
        mock_client.get_account_summary.return_value = fresh_data
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()
        time.sleep(0.3)

        assert controller.is_stale is False
        assert controller.status == ConnectionStatus.CONNECTED

    @patch("ib_controller.IBClient")
    def test_data_stale_after_threshold(self, MockIBClient):
        """
        GIVEN data was fetched 6 minutes ago
        AND stale threshold is 5 minutes (default)
        WHEN checking staleness
        THEN is_stale returns True
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        # Data with old timestamp (6 min ago)
        old_data = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
            timestamp=datetime.now() - timedelta(minutes=6),
        )
        mock_client.get_account_summary.return_value = old_data
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()
        time.sleep(0.3)

        assert controller.is_stale is True

    def test_no_data_is_not_stale(self):
        """
        GIVEN no data has been fetched yet (last_data is None)
        WHEN checking staleness
        THEN is_stale returns False (nothing to be stale)
        """
        mock_root = MagicMock()
        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())

        assert controller.is_stale is False

    @patch("ib_controller.IBClient")
    def test_stale_threshold_from_config(self, MockIBClient):
        """
        GIVEN config sets stale_threshold_minutes=1
        AND data was fetched 2 minutes ago
        WHEN checking staleness
        THEN is_stale returns True (because 2 > 1)
        """
        import json
        import tempfile
        import os

        # Create temp config with 1-minute threshold
        config = {
            "ib_connection": {"host": "127.0.0.1", "port": 7496, "client_id": 1, "timeout_seconds": 5},
            "display": {"stale_threshold_minutes": 1},
        }
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(config, config_file)
        config_file.close()

        try:
            mock_root = MagicMock()
            mock_client = MagicMock()
            # Data fetched 2 min ago – stale for a 1-min threshold
            old_data = AccountData(
                cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
                margin_req=500.0, daily_commissions=0.0,
                timestamp=datetime.now() - timedelta(minutes=2),
            )
            mock_client.get_account_summary.return_value = old_data
            mock_client.get_daily_commissions.return_value = 0.0
            MockIBClient.return_value = mock_client

            controller = IBController(
                root=mock_root,
                on_data_received=MagicMock(),
                on_error=MagicMock(),
                config_path=config_file.name,
            )
            controller.fetch_account_data()
            time.sleep(0.3)

            assert controller.is_stale is True
        finally:
            os.unlink(config_file.name)

    @patch("ib_controller.IBClient")
    def test_stale_boundary_exactly_at_threshold(self, MockIBClient):
        """
        GIVEN data was fetched exactly 5 minutes ago (boundary)
        AND stale threshold is 5 minutes
        WHEN checking staleness
        THEN is_stale returns True (threshold is exclusive: >= means stale)
        """
        mock_root = MagicMock()
        mock_client = MagicMock()
        boundary_data = AccountData(
            cash=1000.0, net_liquidation=2000.0, buying_power=4000.0,
            margin_req=500.0, daily_commissions=0.0,
            timestamp=datetime.now() - timedelta(minutes=5),
        )
        mock_client.get_account_summary.return_value = boundary_data
        mock_client.get_daily_commissions.return_value = 0.0
        MockIBClient.return_value = mock_client

        controller = IBController(root=mock_root, on_data_received=MagicMock(), on_error=MagicMock())
        controller.fetch_account_data()
        time.sleep(0.3)

        assert controller.is_stale is True
