# test_ib_client.py – Unit tests for IBClient (Layer 1)
# TDD Phase: RED – these tests are written BEFORE implementation.
#
# Test Plan Reference: test_plan.md §3.4 (Connection Tests)
# Design Reference: design.md §3.2

import sys
import pytest
from unittest.mock import patch, MagicMock

from ib_client import IBClient
from ib_exceptions import IBConnectionError


# =============================================================================
# §3.4 IBClient – Connection Tests
# =============================================================================


class TestIBClientConnect:
    """Tests for IBClient.connect() method."""

    def test_connect_success(self):
        """
        GIVEN IB Gateway is running and accessible on 127.0.0.1:7496
        WHEN connect() is called with valid parameters
        THEN no exception is raised
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()

            # Act & Assert – should NOT raise
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

    def test_connect_refused_raises_connection_error(self):
        """
        GIVEN IB Gateway is NOT running (port 7496 not listening)
        WHEN connect() is called
        THEN IBConnectionError is raised with descriptive message
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.connect.side_effect = ConnectionRefusedError(
            "[Errno 111] Connection refused"
        )

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()

            # Act & Assert
            with pytest.raises(IBConnectionError) as exc_info:
                client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            assert "IB Gateway" in exc_info.value.message or "Connection" in exc_info.value.message

    def test_connect_timeout_raises_connection_error(self):
        """
        GIVEN IB Gateway port is blocked by firewall (connection hangs)
        WHEN connect() is called and timeout exceeds 5 seconds
        THEN IBConnectionError is raised with timeout message
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.connect.side_effect = TimeoutError("Connection timed out")

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()

            # Act & Assert
            with pytest.raises(IBConnectionError) as exc_info:
                client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            assert exc_info.value.message  # Has a message
            # Timeout-specific assertion
            assert "timeout" in exc_info.value.message.lower() or "זמן" in exc_info.value.message

    def test_connect_client_id_in_use_raises_error_with_code_326(self):
        """
        GIVEN another application is already connected with clientId=1
        WHEN connect() is called with the same clientId
        THEN IBConnectionError is raised with error_code=326
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.connect.side_effect = Exception(
            "Couldn't connect to TWS. clientId 1 already in use."
        )

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()

            # Act & Assert
            with pytest.raises(IBConnectionError) as exc_info:
                client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            assert exc_info.value.error_code == 326

    def test_connect_api_disabled_raises_error_with_code_502(self):
        """
        GIVEN IB Gateway is running but API connections are disabled in settings
        WHEN connect() is called
        THEN IBConnectionError is raised with error_code=502
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.connect.side_effect = Exception(
            "API connection refused. API not enabled in Gateway configuration."
        )

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()

            # Act & Assert
            with pytest.raises(IBConnectionError) as exc_info:
                client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            assert exc_info.value.error_code == 502


from ib_exceptions import IBDataError, AccountData


# =============================================================================
# §3.5 IBClient – Account Summary Tests
# =============================================================================


class TestIBClientGetAccountSummary:
    """Tests for IBClient.get_account_summary() method."""

    def _make_account_value(self, tag, value, currency="USD", account="DU123456"):
        """Helper: create a mock AccountValue object matching ib_insync structure."""
        av = MagicMock()
        av.tag = tag
        av.value = value
        av.currency = currency
        av.account = account
        return av

    def test_get_account_summary_not_connected(self):
        """
        GIVEN IBClient has NOT called connect() yet (self._ib is None)
        WHEN get_account_summary() is called
        THEN IBConnectionError is raised
        """
        client = IBClient()
        # _ib is None – never connected

        with pytest.raises(IBConnectionError):
            client.get_account_summary()

    def test_get_account_summary_all_fields(self):
        """
        GIVEN IBClient is connected and IB returns all 4 account fields
        WHEN get_account_summary() is called
        THEN returns AccountData with all fields populated and is_partial=False
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.accountSummary.return_value = [
            self._make_account_value("TotalCashValue", "12450.50"),
            self._make_account_value("NetLiquidation", "24830.75"),
            self._make_account_value("BuyingPower", "49661.00"),
            self._make_account_value("FullMaintMarginReq", "3200.25"),
        ]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_account_summary()

        # Assert
        assert isinstance(result, AccountData)
        assert result.cash == 12450.50
        assert result.net_liquidation == 24830.75
        assert result.buying_power == 49661.00
        assert result.margin_req == 3200.25
        assert result.is_partial is False
        assert result.missing_fields == []

    def test_get_account_summary_partial_data(self):
        """
        GIVEN IB returns only 2 out of 4 expected fields
        WHEN get_account_summary() is called
        THEN returns AccountData with is_partial=True and missing_fields lists the 2 missing
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.accountSummary.return_value = [
            self._make_account_value("TotalCashValue", "12450.50"),
            self._make_account_value("NetLiquidation", "24830.75"),
            # Missing: BuyingPower, FullMaintMarginReq
        ]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_account_summary()

        # Assert
        assert isinstance(result, AccountData)
        assert result.cash == 12450.50
        assert result.net_liquidation == 24830.75
        assert result.is_partial is True
        assert len(result.missing_fields) == 2
        assert "BuyingPower" in result.missing_fields
        assert "FullMaintMarginReq" in result.missing_fields

    def test_get_account_summary_empty_response(self):
        """
        GIVEN IB returns an empty list (no account data at all)
        WHEN get_account_summary() is called
        THEN IBDataError is raised
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.accountSummary.return_value = []

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act & Assert
            with pytest.raises(IBDataError) as exc_info:
                client.get_account_summary()

            assert "נתונים" in exc_info.value.message or "data" in exc_info.value.message.lower()

    def test_get_account_summary_correct_float_parsing(self):
        """
        GIVEN IB returns values as strings (as ib_insync does)
        WHEN get_account_summary() is called
        THEN values are correctly parsed to float
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.accountSummary.return_value = [
            self._make_account_value("TotalCashValue", "1234567.89"),
            self._make_account_value("NetLiquidation", "0.01"),
            self._make_account_value("BuyingPower", "-500.00"),
            self._make_account_value("FullMaintMarginReq", "0"),
        ]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_account_summary()

        # Assert – correct type and value conversion
        assert result.cash == 1234567.89
        assert result.net_liquidation == 0.01
        assert result.buying_power == -500.00
        assert result.margin_req == 0.0
        assert all(isinstance(v, float) for v in [
            result.cash, result.net_liquidation, result.buying_power, result.margin_req
        ])



from datetime import datetime, date


# =============================================================================
# §3.6 IBClient – Daily Commissions Tests
# =============================================================================


class TestIBClientGetDailyCommissions:
    """Tests for IBClient.get_daily_commissions() method."""

    def _make_fill(self, commission, exec_time):
        """Helper: create a mock Fill object matching ib_insync structure.

        ib_insync Fill structure:
            fill.commissionReport.commission → float
            fill.execution.time → datetime
        """
        fill = MagicMock()
        fill.commissionReport.commission = commission
        fill.execution.time = exec_time
        return fill

    def test_get_daily_commissions_not_connected(self):
        """
        GIVEN IBClient has NOT called connect() (self._ib is None)
        WHEN get_daily_commissions() is called
        THEN IBConnectionError is raised
        """
        client = IBClient()

        with pytest.raises(IBConnectionError):
            client.get_daily_commissions()

    def test_get_daily_commissions_with_fills_today(self):
        """
        GIVEN IB returns 3 fills from today with commissions 2.50, 3.00, 1.50
        WHEN get_daily_commissions() is called
        THEN returns 7.00 (sum of today's commissions)
        """
        # Arrange
        today = datetime.now()
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.fills.return_value = [
            self._make_fill(2.50, today.replace(hour=9, minute=30)),
            self._make_fill(3.00, today.replace(hour=10, minute=15)),
            self._make_fill(1.50, today.replace(hour=14, minute=45)),
        ]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_daily_commissions()

        # Assert
        assert result == 7.00
        assert isinstance(result, float)

    def test_get_daily_commissions_no_fills_today(self):
        """
        GIVEN IB returns an empty fills list (no executions today)
        WHEN get_daily_commissions() is called
        THEN returns 0.0
        """
        # Arrange
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.fills.return_value = []

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_daily_commissions()

        # Assert
        assert result == 0.0

    def test_get_daily_commissions_filters_old_dates(self):
        """
        GIVEN IB returns 3 fills: 2 from today, 1 from yesterday
        WHEN get_daily_commissions() is called
        THEN returns sum of only today's commissions (ignores yesterday)
        """
        # Arrange
        today = datetime.now()
        yesterday = today.replace(day=today.day - 1) if today.day > 1 else today.replace(month=today.month - 1, day=28)

        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.fills.return_value = [
            self._make_fill(4.00, today.replace(hour=9, minute=30)),      # today
            self._make_fill(5.50, today.replace(hour=11, minute=0)),      # today
            self._make_fill(99.99, yesterday.replace(hour=15, minute=0)), # yesterday – must be excluded
        ]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_daily_commissions()

        # Assert – only today's fills counted
        assert result == 9.50
        assert result != 109.49  # yesterday's 99.99 must NOT be included

    def test_get_daily_commissions_handles_none_commission(self):
        """
        GIVEN IB returns a fill where commissionReport.commission is None or invalid
        WHEN get_daily_commissions() is called
        THEN that fill is skipped gracefully, no crash
        """
        # Arrange
        today = datetime.now()
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True

        fill_good = self._make_fill(3.00, today.replace(hour=10, minute=0))
        fill_bad = MagicMock()
        fill_bad.commissionReport.commission = None  # Invalid
        fill_bad.execution.time = today.replace(hour=11, minute=0)

        mock_ib_instance.fills.return_value = [fill_good, fill_bad]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_daily_commissions()

        # Assert – only the valid fill is summed
        assert result == 3.00

    def test_get_daily_commissions_returns_rounded_float(self):
        """
        GIVEN IB returns fills with commissions that produce floating-point imprecision
        WHEN get_daily_commissions() is called
        THEN result is properly rounded to 2 decimal places
        """
        # Arrange
        today = datetime.now()
        mock_ib_instance = MagicMock()
        mock_ib_instance.isConnected.return_value = True
        mock_ib_instance.fills.return_value = [
            self._make_fill(1.1, today.replace(hour=9, minute=30)),
            self._make_fill(2.2, today.replace(hour=10, minute=0)),
        ]

        with patch("ib_client.ib_insync.IB", return_value=mock_ib_instance):
            client = IBClient()
            client.connect(host="127.0.0.1", port=7496, client_id=1, timeout=5)

            # Act
            result = client.get_daily_commissions()

        # Assert – no floating point weirdness like 3.3000000000000003
        assert result == 3.30
